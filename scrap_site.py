import argparse
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin

import httpx
import pandas as pd
from bs4 import BeautifulSoup, Tag

BASE_URL = "https://kotobaka.ru/korma-dlya-sobak"
COLUMNS = ["name", "weight", "price", "old_price", "cashback", "url"]


def parse_price(text: str) -> int | None:
    """Извлечь целую цену перед «р.», убрав разделители с пробелом"""
    match = re.search(r"(\d[\d\s]*)\s*р\.", text)
    return int(re.sub(r"\s+", "", match.group(1))) if match else None


def parse_product(item: Tag, page_url: str) -> list[dict]:
    """Вернуть отдельную строку для каждой распознанной фасовки корма"""
    name_tag = item.select_one("h4 a")
    if name_tag is None:
        return []

    name = name_tag.get_text(strip=True)
    href = name_tag.get("href")
    product_url = urljoin(page_url, href if isinstance(href, str) else "")
    price_new = item.select_one(".price-new")
    price_old = item.select_one(".price-old")

    if price_new is not None:
        return [
            {
                "name": name,
                "weight": None,
                "price": parse_price(price_new.get_text(strip=True)),
                "old_price": (
                    parse_price(price_old.get_text(strip=True))
                    if price_old is not None
                    else None
                ),
                "cashback": None,
                "url": product_url,
            }
        ]

    # Вторая структура: элементы .price чередуются вес, цена
    rows = []
    elements = item.select(".price")
    for i in range(0, len(elements) - 1, 2):
        weight = elements[i].get_text(" ", strip=True)
        price_text = elements[i + 1].get_text(" ", strip=True)
        price = parse_price(price_text)
        if price is None:
            continue

        cashback = re.search(r"Кэшбэк:\s*(\d+)", price_text)
        rows.append(
            {
                "name": name,
                "weight": weight,
                "price": price,
                "old_price": None,
                "cashback": int(cashback.group(1)) if cashback else None,
                "url": product_url,
            }
        )
    return rows


def collect_products() -> pd.DataFrame:
    """Обойти страницы каталога до отсутствия следующей ссылки"""
    url = BASE_URL
    all_items = []
    visited_urls = set()

    with httpx.Client(
        follow_redirects=True,
        timeout=30,
        headers={"User-Agent": "Mozilla/5.0"},
    ) as client:
        while url:
            if url in visited_urls:
                print("Повторная ссылка, обход завершён:", url)
                break
            visited_urls.add(url)

            response = client.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            items = soup.select("div.product-layout")
            if not items:
                print("Товары не найдены:", url)
                break

            for item in items:
                all_items.extend(parse_product(item, url))

            print(
                f"Страница: {url} | Карточек: {len(items)} | "
                f"Всего строк: {len(all_items)}"
            )
            next_page = soup.select_one('link[rel="next"][href]')
            next_href = next_page.get("href") if next_page is not None else None
            url = urljoin(url, next_href) if isinstance(next_href, str) else None
            if url:
                time.sleep(1)

    return pd.DataFrame(all_items, columns=COLUMNS)


def clean_products(df: pd.DataFrame) -> pd.DataFrame:
    """Выполнить преодобработку данных"""
    df = df.copy()
    for column in ["price", "old_price", "cashback"]:
        df[column] = pd.to_numeric(df[column], errors="coerce").astype("Int64")

    df["name"] = (
        df["name"].astype("string").str.strip().str.replace(r"\s+", " ", regex=True)
    )
    df["weight_kg"] = pd.to_numeric(
        df["weight"]
        .astype("string")
        .str.extract(r"(\d+(?:[.,]\d+)?)\s*кг", expand=False)
        .str.replace(",", ".", regex=False),
        errors="coerce",
    )
    return df


def print_summary(df: pd.DataFrame) -> None:
    """Вывести основную информацию"""
    print(f"\nРазмер таблицы: {df.shape}")
    print(f"Уникальных названий: {df['name'].nunique()}")
    print("\nПервые 10 строк:")
    print(df.head(10).to_string(index=False))
    print("\nСлучайные строки:")
    print(df.sample(min(10, len(df))).to_string(index=False))
    print("\nИнформация о таблице:")
    df.info()
    print("\nПропуски:")
    print(df.isna().sum().to_string())
    print("\nДубликаты по ссылке и весу:", df.duplicated(["url", "weight"]).sum())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "data" / "dog_food.csv",
        help="путь итогового CSV",
    )
    args = parser.parse_args()
    args.output = args.output.expanduser().resolve()
    try:
        df = clean_products(collect_products())
        if df.empty:
            print("Не удалось собрать товары. CSV не сохранён.", file=sys.stderr)
            return 1

        args.output.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(args.output, index=False, encoding="utf-8-sig")
        print_summary(df)
        print(f"\nСохранено: {args.output.resolve()}")
    except (httpx.HTTPError, OSError) as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nСбор прерван пользователем.", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
