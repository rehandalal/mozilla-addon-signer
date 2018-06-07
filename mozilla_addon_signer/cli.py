import base64
import json
import os
import subprocess
import tempfile
import traceback

import boto3
import click

from botocore.exceptions import NoRegionError
from colorama import Fore

from mozilla_addon_signer.bugzilla import BugzillaAPI
from mozilla_addon_signer.config import config
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


CONFIG_WIZARD_STEPS = [
    ('aws.profile_name', 'Default AWS Profile'),
    ('bugzilla.api_key', 'Default Bugzilla API Key'),
]


def load_xpi(fp):
    try:
        xpi = XPI(fp)
    except XPI.DoesNotExist:
        output('ERROR: `{}` does not exist.'.format(fp), Fore.RED)
        exit(1)
    except XPI.BadZipfile:
        output('ERROR: `{}` could not be unzipped.'.format(fp), Fore.RED)
        exit(1)
    except XPI.InvalidXPI:
        output('ERROR: `{}` is not a valid web extension.'.format(fp), Fore.RED)
        exit(1)
    return xpi


@click.group()
def cli():
    pass


@cli.command()
@click.argument('key', nargs=1, required=False)
@click.argument('value', nargs=1, required=False)
def configure(key, value):
    """Configure defaults for this tool."""
    if key and value:
        config.set(key, value)
        config.save()
    elif key:
        output(config.get(key, ''))
    else:
        for key, name in CONFIG_WIZARD_STEPS:
            if config.has(key):
                output('{} is already set to: {}'.format(name, config.get(key)))
                if not click.confirm('Do you want to change this value?'):
                    output('')
                    continue
            value = click.prompt(name, default='') or None
            config.set(key, value)

        config.save()


@cli.command()
@click.option('--addon-type', '-t', help='The type of addon that you want to sign.')
@click.option('--api-key', '-k', default=None, help='The Bugzilla API key to use.')
@click.option('--attach', '-b', default=None, help='Attach the signed addon to a bug.')
@click.option('--bucket-name', default=None, help='The S3 bucket to upload the file to.')
@click.option('--env', '-e', default=DEFAULT_ENV, help='The environment to sign in.')
@click.option('--profile', '-p', default=None, help='The name of the AWS profile to use.')
@click.option('--verbose', '-v', is_flag=True)
@click.argument('src', nargs=1)
@click.argument('dest', nargs=1, required=False)
@click.pass_context
def sign(ctx, src, dest, addon_type, api_key, attach, bucket_name, env, profile, verbose,
         **kwargs):
    """Uploads and signs an addon XPI file."""
    xpi = load_xpi(src)

    if not dest:
        dest = xpi.suggested_filename(mark_signed=True)

    # Check if the XPI is already signed
    if xpi.is_signed:
        output('WARNING: XPI file is already signed.', Fore.YELLOW)
        if not click.confirm('Are you sure you want to sign this file?'):
            output('Aborted!')
            exit(1)

    # Validate the addon type
    if addon_type not in ADDON_TYPES:
        if addon_type:
            output('WARNING: You did not provide a valid addon type.\n', Fore.YELLOW)
        addon_type = prompt_choices('Addon Type', ADDON_TYPES)

    # Validate the environment
    if env not in ENV_OPTIONS:
        output('WARNING: You did not provide a valid environment.\n', Fore.YELLOW)
        env = prompt_choices('Environment', ENV_OPTIONS, default=0)

    profile = profile or config.get('aws.profile_name', default=None)

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
    if 'uploaded' in data:
        uploaded = data['uploaded']
        output('Successfully signed!', Fore.GREEN)
    else:
        output('ERROR: Something went wrong!', Fore.RED)
        exit(1)

    should_download = not attach

    while should_download and os.path.exists(dest):
        output('\nWARNING: `{}` already exists.'.format(dest), Fore.YELLOW)
        should_download = click.confirm('Do you want to overwrite this file?')
        if not should_download and click.confirm('Would you like to pick another destination?'):
            dest = click.prompt('Choose another destination path')
            should_download = True

    if should_download:
        output_bucket = s3.Bucket(uploaded.get('bucket'))
        output_bucket.download_file(uploaded.get('key'), dest)
    elif attach and 'uploaded' in data:
        api_key = api_key or config.get('bugzilla.api_key', default=None)
        bz = BugzillaAPI(api_key)
        signed_xpi = s3.Object(uploaded.get('bucket'), uploaded.get('key'))
        attachment_data = base64.b64encode(signed_xpi.get()['Body'].read())
        bz.create_attachment_for_bug(attach, attachment_data=attachment_data, file_name=dest,
                                     summary=dest, content_type='application/x-xpinstall')
        output('Attachment successfully created!', Fore.GREEN)
    else:
        output('\n{}'.format(json.dumps(data, indent=2, sort_keys=True)))

    ctx.invoke(check_needinfo, bug_number=attach, **kwargs)


@cli.command()
@click.option('--api-key', '-k', default=None, help='The Bugzilla API key to use.')
@click.argument('bug_number', nargs=1)
def check_needinfo(bug_number, api_key):
    """Checks for an open needinfo on the given bug, and offers to clear it."""
    api_key = api_key or config.get('bugzilla.api_key', default=None)
    bz = BugzillaAPI(api_key)
    bug = bz.get_bug(bug_number)
    flags = bug.get_flags()

    user_email = bz.who_am_i()['name']
    for flag in flags:
        needs_info = flag['name'] == 'needinfo' and flag['status'] == '?'
        if needs_info and flag['requestee'] == user_email:
            if click.confirm('Clear your needinfo from {}?'.format(flag['setter'])):
                bug.set_flags([{'id': flag['id'], 'status': 'X'}])
                output('Needinfo cleared', Fore.GREEN)
            break


@cli.command()
@click.option('--addon-type', '-t', help='The type of addon that you want to sign.')
@click.option('--bucket-name', default=None, help='The S3 bucket to upload the file to.')
@click.option('--env', '-e', default=DEFAULT_ENV, help='The environment to sign in.')
@click.option('--profile', '-p', default=None, help='The name of the AWS profile to use.')
@click.option('--verbose', '-v', is_flag=True)
@click.option('--api-key', '-k', default=None, help='The Bugzilla API key to use.')
@click.option('--include-obsolete', '-o', is_flag=True)
@click.option('--no-attach', is_flag=True, help='Do not reattach the signed XPI to the bug.')
@click.argument('bug_number', nargs=1)
@click.argument('dest', nargs=1, required=False)
@click.pass_context
def sign_from_bug(ctx, bug_number, api_key, include_obsolete, no_attach, **kwargs):
    api_key = api_key or config.get('bugzilla.api_key', default=None)
    bz = BugzillaAPI(api_key)
    attachments = bz.get_attachments_for_bug(bug_number)

    if not no_attach:
        kwargs['attach'] = bug_number

    choices = []
    for a in attachments:
        if not a.get('is_obsolete', 0) or include_obsolete:
            content_type = a.get('content_type')
            if content_type in ['application/x-xpinstall', 'application/zip']:
                choices.append(a)

    attachment = prompt_choices(
        'Select attachment', choices,
        name_parser=lambda i: '{} by {}'.format(i['summary'], i['creator']))

    attachment_data = bz.get_attachment_data(attachment['id'])

    tmpdir = tempfile.mkdtemp()
    tmppath = os.path.join(tmpdir, attachment['file_name'])
    with open(tmppath, 'wb') as f:
        f.write(base64.b64decode(attachment_data))

    ctx.invoke(sign, src=tmppath, **kwargs)


@cli.command()
@click.argument('src', nargs=1)
def show_cert(src):
    """Inspect the certificate for a signed addon."""
    xpi = load_xpi(src)

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
