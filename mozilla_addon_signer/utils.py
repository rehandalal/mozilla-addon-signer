from colorama import Style


def output(str, *styles):
    print(Style.RESET_ALL, end='')
    if styles:
        print(*styles, end='')
    print(str, end='')
    print(Style.RESET_ALL)
