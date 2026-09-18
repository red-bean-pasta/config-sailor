from config_sailor import arg_parser
from config_sailor.utils import logging_helper


def main():
    known, unknown = arg_parser.parse_args()

    logging_helper.initialize(getattr(known, "log_level", "debug"))

    if unknown:
        known.func(known, unknown)
    else:
        known.func(known)


if __name__ == "__main__":
    main()