from pathlib import Path

import gdown
import pandas as pd

DATA_URL = "https://drive.google.com/uc?id=1Bj9C5NBc6cEi3SFhE-WCLmxxfzxfIxsi"

INPUT_FILE = Path("dataset.csv")
TEMP_FILE = Path("dataset.csv.part")
OUTPUT_FILE = Path("gold_apple.parquet")

CATEGORY_COLUMNS = ("Категория", "Тип продукта", "Бренд")
NUMERIC_COLUMNS = ("Цена", "Старая цена", "Объем")


def load_data():
    if not INPUT_FILE.exists():
        downloaded_file = gdown.download(DATA_URL, str(TEMP_FILE), quiet=False)

        if downloaded_file is None:
            raise RuntimeError("Не удалось скачать датасет")

        TEMP_FILE.replace(INPUT_FILE)

    return pd.read_csv(
        INPUT_FILE,
        sep=";",
        encoding="utf-8-sig",
        dtype="string",
        keep_default_na=False,
        na_values=[""],
    )


def convert_types(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    for column in CATEGORY_COLUMNS:
        df[column] = df[column].astype("category")

    for column in NUMERIC_COLUMNS:
        values = df[column].str.strip().str.replace(",", ".", regex=False)
        dtype = "Float64" if column == "Объем" else "Int64"
        df[column] = pd.to_numeric(values, errors="raise").astype(dtype)

    df["Дата обновления"] = pd.to_datetime(
        df["Дата обновления"],
        format="%d.%m.%Y",
        errors="raise",
    )

    return df


if __name__ == "__main__":
    data = load_data()
    data = convert_types(data)
    data.to_parquet(OUTPUT_FILE, engine="pyarrow", index=False)

    print(data.dtypes)
    print(data.head(10))
