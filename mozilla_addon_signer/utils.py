import click

from colorama import Style
from six import print_


def output(str, *styles):
    print_(Style.RESET_ALL, end='')
    if styles:
        print_(*styles, end='')
    print_(str, end='')
    print_(Style.RESET_ALL)


def prompt_choices(text, choices, default=None, name_parser=None):
    output('Please select one of the following:')

    for i, value in enumerate(choices):
        name = name_parser(value) if name_parser else value
        output('[{}] {}'.format(i, name))

    index = None

    while index is None or index < 0 or index >= len(choices):
        index = click.prompt('\n{}'.format(text), type=int, default=default)

    output('')

    return choices[index]
