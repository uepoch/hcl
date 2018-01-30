#!/bin/env python3


def greet(name="Anonymous"):
    return "Hello %s" % name


def main():
    print(greet())


if __name__ == '__main__':
    main()
