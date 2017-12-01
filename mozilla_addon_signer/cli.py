import configparser
import json
import os
import traceback

from hashlib import sha256

import boto3
import click

from botocore.exceptions import NoRegionError
from colorama import Fore

from mozilla_addon_signer import CONFIG_PATH
from mozilla_addon_signer.utils import output


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

    # Save the config
    with open(CONFIG_PATH, 'w') as f:
        config.write(f)


@cli.command()
@click.option('--addon-type', '-t', help='The type of addon that you want to sign.')
@click.option('--bucket-name', default=None, help='The S3 bucket to upload the file to.')
@click.option('--env', '-e', default=DEFAULT_ENV, help='The environment to sign in.')
@click.option('--profile', '-p', default=None, help='The name of the AWS profile to use.')
@click.option('--verbose', '-v', is_flag=True)
@click.argument('src', type=click.File('rb'), nargs=1)
@click.argument('dest', nargs=1, required=False)
def sign(src, dest, addon_type, bucket_name, env, profile, verbose):
    """Uploads and signs an addon XPI file."""

    # Validate the addon type
    if addon_type not in ADDON_TYPES:
        output('WARNING: You did not provide a valid addon type.', Fore.YELLOW)
        output('\nPlease select one of the following:')
        for i, value in enumerate(ADDON_TYPES):
            output('[{}] {}'.format(i, value))
        index = None
        while index is None or index < 0 or index >= len(ADDON_TYPES):
            index = click.prompt('\nAddon Type', type=int)
        output('')
        addon_type = ADDON_TYPES[index]

    # Validate the environment
    if env not in ENV_OPTIONS:
        output('WARNING: You did not provide a valid environment.', Fore.YELLOW)
        output('\nPlease select one of the following:')
        for i, value in enumerate(ENV_OPTIONS):
            output('[{}] {}'.format(i, value))
        index = None
        while index is None or index < 0 or index >= len(ENV_OPTIONS):
            index = click.prompt('\nEnvironment', type=int, default=0)
        output('')
        env = ENV_OPTIONS[index]

    profile = profile or config.get('aws', 'profile_name', fallback=None)

    # Boto setup
    session = boto3.Session(profile_name=profile)
    s3 = session.resource('s3')

    try:
        aws_lambda = session.client('lambda')
    except NoRegionError:
        output('ERROR: You must specify a region.', Fore.RED)
        exit(1)

    # Get the hash of the XPI file
    xpi_hash = sha256(src.read()).hexdigest()
    src.seek(0)

    # Upload the XPI file to the S3 bucket
    input_bucket_name = bucket_name or 'net-mozaws-{}-addons-signxpi-input'.format(env)
    input_bucket = s3.Bucket(input_bucket_name)
    key = os.path.basename(src.name)
    input_bucket.put_object(Body=src, Key=key)

    # Invoke AWS Lambda function
    function_name = 'addons-sign-xpi-{}-{}'.format(addon_type, env)
    lambda_args = {
        'source': {
            'bucket': input_bucket_name,
            'key': key,
        },
        'checksum': xpi_hash,
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
    if dest and 'uploaded' in data:
        uploaded = data['uploaded']
        output_bucket = s3.Bucket(uploaded.get('bucket'))
        output_bucket.download_file(uploaded.get('key'), dest)
    else:
        output('\n{}'.format(json.dumps(data, indent=2, sort_keys=True)))
