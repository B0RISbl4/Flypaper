"""Download an AirHex logo, remove its PREVIEW watermark, and save it."""

import argparse
import sys

from curl_cffi import requests

import remove_preview

URL_TEMPLATE = "https://content.airhex.com/content/logos/airlines_{code}_{width}_{height}_t.png"
MAX_DIMENSION = 2048


def airline_code(value):
    if len(value) != 2 or not value.isascii() or not value.isalnum():
        raise argparse.ArgumentTypeError(
            "код авиакомпании должен состоять из двух букв или цифр"
        )
    return value.upper()


def download_airline_tail(code, output, width=600, height=600):
    """Download and clean an airline tail image into a PNG file."""
    code = airline_code(code)
    url = URL_TEMPLATE.format(code=code, width=width, height=height)
    response = requests.get(url, impersonate="chrome", timeout=30)
    content_type = response.headers.get("content-type", "")
    if not content_type.lower().startswith("image/"):
        raise ValueError(
            f"сервер не вернул изображение: HTTP {response.status_code}, "
            f"Content-Type: {content_type or 'не указан'}"
        )

    try:
        X, has_alpha, dtype = remove_preview.load_image(response.content)
    except SystemExit as exc:
        raise ValueError(str(exc)) from exc

    image_height, image_width = X.shape[:2]
    if (image_width, image_height) != (width, height):
        raise ValueError(
            f"сервер вернул изображение {image_width}x{image_height}, "
            f"ожидалось {width}x{height}"
        )

    if not 200 <= response.status_code < 300:
        print(
            f"предупреждение: HTTP {response.status_code}, "
            "но содержимое является корректным изображением",
            file=sys.stderr,
        )

    result = remove_preview.remove_image(X)
    remove_preview.save_image(output, result, has_alpha, dtype)


def image_dimension(value):
    try:
        dimension = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("размер должен быть целым числом") from exc
    if not 1 <= dimension <= MAX_DIMENSION:
        raise argparse.ArgumentTypeError(f"размер должен быть от 1 до {MAX_DIMENSION}")
    return dimension


def main():
    parser = argparse.ArgumentParser(
        description="Скачать изображение AirHex, удалить PREVIEW и сохранить результат."
    )
    parser.add_argument("width", type=image_dimension, help="ширина исходного изображения")
    parser.add_argument("height", type=image_dimension, help="высота исходного изображения")
    parser.add_argument("code", type=airline_code, help="двухсимвольный код из букв и цифр")
    args = parser.parse_args()

    output = f"{args.code}.png"
    try:
        download_airline_tail(args.code, output, args.width, args.height)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    print(f"готово: {output}")


if __name__ == "__main__":
    main()
