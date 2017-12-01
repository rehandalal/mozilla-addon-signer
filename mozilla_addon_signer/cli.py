import base64
import configparser
import json
import os
import subprocess
import tempfile
import traceback

import boto3
import click

from botocore.exceptions import NoRegionError
from colorama import Fore

from mozilla_addon_signer import CONFIG_PATH
from mozilla_addon_signer.bugzilla import BugzillaAPI
from mozilla_addon_signer.utils import output, prompt_choices
from mozilla_addon_signer.xpi import XPI


ADDON_TYPES = [
    'system',
    'mozillaextension',
]

DEFAULT_ENV = 'prod'
ENV_OPTIONS = [
    DEFAULT_ENV,
    'stage',
]


with open(CONFIG_PATH, 'a+') as f:
    f.seek(0)
    config = configparser.ConfigParser()
    config.read_file(f)


def update_config(section, option, value):
    if not section in config:
        config[section] = {}
    if value is None and option in config[section]:
        del config[section][option]
    elif value is not None:
        config[section][option] = value


@click.group()
def cli():
    pass


@cli.command()
def configure():
    """Configure defaults for this tool."""

    # Update the default AWS profile
    profile_name = click.prompt('Default AWS Profile', default='') or None
    update_config('aws', 'profile_name', profile_name)

    # Update the default bugzilla API key
    bugzilla_api_key = click.prompt('Default Bugzilla API Key', default='') or None
    update_config('bugzilla', 'api_key', bugzilla_api_key)

    # Save the config
    with open(CONFIG_PATH, 'w') as f:
        config.write(f)


@cli.command()
@click.option('--addon-type', '-t', help='The type of addon that you want to sign.')
@click.option('--bucket-name', default=None, help='The S3 bucket to upload the file to.')
@click.option('--env', '-e', default=DEFAULT_ENV, help='The environment to sign in.')
@click.option('--profile', '-p', default=None, help='The name of the AWS profile to use.')
@click.option('--verbose', '-v', is_flag=True)
@click.argument('src', nargs=1)
@click.argument('dest', nargs=1, required=False)
def sign(src, dest, addon_type, bucket_name, env, profile, verbose):
    """Uploads and signs an addon XPI file."""
    try:
        xpi = XPI(src)
    except XPI.DoesNotExist:
        output('ERROR: `{}` does not exist.'.format(src), Fore.RED)
        exit(1)
    except XPI.BadZipfile:
        output('ERROR: `{}` could not be unzipped.'.format(src), Fore.RED)
        exit(1)

    # Check if the XPI is already signed
    if xpi.is_signed:
        output('WARNING: XPI file is already signed.', Fore.YELLOW)
        if not click.confirm('Are you sure you want to sign this file?'):
            output('Aborted!')
            exit(1)

    # Validate the addon type
    if addon_type not in ADDON_TYPES:
        output('WARNING: You did not provide a valid addon type.\n', Fore.YELLOW)
        addon_type = prompt_choices('Addon Type', ADDON_TYPES)

    # Validate the environment
    if env not in ENV_OPTIONS:
        output('WARNING: You did not provide a valid environment.\n', Fore.YELLOW)
        env = prompt_choices('Environment', ENV_OPTIONS, default=0)

    profile = profile or config.get('aws', 'profile_name', fallback=None)

    # Boto setup
    session = boto3.Session(profile_name=profile)
    s3 = session.resource('s3')

    try:
        aws_lambda = session.client('lambda')
    except NoRegionError:
        output('ERROR: You must specify a region.', Fore.RED)
        exit(1)

    # Upload the XPI file to the S3 bucket
    input_bucket_name = bucket_name or 'net-mozaws-{}-addons-signxpi-input'.format(env)
    input_bucket = s3.Bucket(input_bucket_name)
    key = os.path.basename(src)
    input_bucket.put_object(Body=xpi.open(), Key=key)

    # Invoke AWS Lambda function
    function_name = 'addons-sign-xpi-{}-{}'.format(addon_type, env)
    lambda_args = {
        'source': {
            'bucket': input_bucket_name,
            'key': key,
        },
        'checksum': xpi.sha256sum,
    }
    response = aws_lambda.invoke(
        FunctionName=function_name,
        Payload=json.dumps(lambda_args)
    )

    payload = response['Payload'].read()

    try:
        data = json.loads(payload)
    except Exception as e:
        output("ERROR Couldn't parse response: {} {}".format(e, payload), Fore.RED)
        exit(1)

    if response['StatusCode'] >= 300 or 'FunctionError' in response:
        output('ERROR: Invoking lambda failed.', Fore.RED)
        if verbose:
            if 'stackTrace' in data:
                tb_out = ''.join(traceback.format_list(data['stackTrace']))
                output(tb_out.rstrip('\n'))
            error_type = data.get('errorType', 'No error type')
            error_msg = data.get('errorMessage')
            error_out = error_type
            if error_msg:
                error_out = '{}: {}'.format(error_type, error_msg)
            output(error_out)
        exit(1)

    # Download the file or dump the data
    output('Successfully signed!', Fore.GREEN)

    should_download = dest and 'uploaded' in data
    while should_download and os.path.exists(dest):
        output('\nWARNING: `{}` already exists.'.format(dest), Fore.YELLOW)
        should_download = click.confirm('Do you want to overwrite this file?')
        if not should_download and click.confirm('Would you like to pick another destination?'):
            dest = click.prompt('Choose another destination path')
            should_download = True

    if should_download:
        uploaded = data['uploaded']
        output_bucket = s3.Bucket(uploaded.get('bucket'))
        output_bucket.download_file(uploaded.get('key'), dest)
    else:
        output('\n{}'.format(json.dumps(data, indent=2, sort_keys=True)))


@cli.command()
@click.option('--addon-type', '-t', help='The type of addon that you want to sign.')
@click.option('--api-key', '-k', default=None, help='The Bugzilla API key to use.')
@click.option('--bucket-name', default=None, help='The S3 bucket to upload the file to.')
@click.option('--env', '-e', default=DEFAULT_ENV, help='The environment to sign in.')
@click.option('--include-obsolete', '-o', is_flag=True)
@click.option('--profile', '-p', default=None, help='The name of the AWS profile to use.')
@click.option('--verbose', '-v', is_flag=True)
@click.argument('bug_number', nargs=1)
@click.argument('dest', nargs=1, required=False)
@click.pass_context
def sign_from_bug(ctx, bug_number, dest, addon_type, api_key, bucket_name, env, include_obsolete,
                  profile, verbose):
    api_key = api_key or config.get('bugzilla', 'api_key', fallback=None)
    bz = BugzillaAPI(api_key)
    attachments = bz.get_attachments_for_bug(bug_number)

    choices = []
    for a in attachments:
        if not a.get('is_obsolete', 0) or include_obsolete:
            if a.get('content_type') == 'application/x-xpinstall':
                choices.append(a)

    attachment = prompt_choices(
        'Select attachment', choices, name_parser=lambda i: '{} by {}'.format(i['summary'], i['creator']))

    attachment_data = bz.get_attachment_data(attachment['id'])

    tmpdir = tempfile.mkdtemp()
    tmppath = os.path.join(tmpdir, attachment['file_name'])
    with open(tmppath, 'wb') as f:
        f.write(base64.b64decode(attachment_data))

    ctx.invoke(sign, src=tmppath, dest=dest, addon_type=addon_type, bucket_name=bucket_name,
               env=env, profile=profile, verbose=verbose)


@cli.command()
@click.argument('src', nargs=1)
def show_cert(src):
    """Inspect the certificate for a signed addon."""
    try:
        xpi = XPI(src)
    except XPI.DoesNotExist:
        output('ERROR: `{}` does not exist.'.format(src), Fore.RED)
        exit(1)
    except XPI.BadZipfile:
        output('ERROR: `{}` could not be unzipped.'.format(src), Fore.RED)
        exit(1)

    if not xpi.is_signed:
        output('ERROR: Source file is not a signed addon.', Fore.RED)
        exit(1)

    cmd = 'openssl pkcs7  -inform der -in {} -print_certs -text'.format(xpi.certificate_path)
    process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
    out, err = process.communicate()

    if err:
        output('An error occured!', Fore.RED)
        output(err.decode())
    else:
        output(out.decode())
