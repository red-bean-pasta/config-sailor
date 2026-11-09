import multiprocessing

from config_sailor import arg_parser
from config_sailor.utils import logging_helper


def main():
    multiprocessing.freeze_support()
    args = arg_parser.parse_args()

    logging_helper.initialize(getattr(args, "log_level", "debug"))
    args.func(args)


if __name__ == "__main__":
    main()