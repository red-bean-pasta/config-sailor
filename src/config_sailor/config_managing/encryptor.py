from pathlib import Path

from config_sailor.encrypt import encryptor


def encrypt(
        input_path: str | Path,
        output_path: str | Path | None,
) -> str:
    i = Path(input_path)
    if output_path:
        o = Path(output_path)
    elif i.suffix == ".json":
        o = i.with_suffix(".enc")
    else:
        o = i.with_name(i.name + ".enc")
    key = encryptor.generate_key_and_encrypt_file(i, o)
    return key
