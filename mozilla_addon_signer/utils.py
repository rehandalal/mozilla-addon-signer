import click

from colorama import Style


def output(str, *styles):
    print(Style.RESET_ALL, end='')
    if styles:
        print(*styles, end='')
    print(str, end='')
    print(Style.RESET_ALL)


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
