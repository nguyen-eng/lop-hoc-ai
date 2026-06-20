# Lop hoc AI tuong tac

Ban nang cap tap trung vao chay muot hon khi co nhieu hoc vien:

- Luu phan hoi vao SQLite thay vi CSV rieng le.
- Bat SQLite WAL de giao vien doc dashboard trong khi hoc vien van ghi du lieu.
- Gom token, cau hinh, ngan hang cau hoi va database vao thu muc `data/`.
- Giam live refresh mac dinh tu 1.5 giay xuong 3 giay, co the doi bang `APP_LIVE_REFRESH_MS`.
- Gioi han cache bang `APP_CACHE_TTL_SECONDS` va `APP_MAX_CACHE_ENTRIES`.
- Hoc vien van o che do submit-only de tranh moi may hoc vien deu refresh ket qua lop.

## Chay local

```sh
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Mo `http://localhost:8501`.

## Bien moi truong

```text
GEMINI_API_KEY=...
APP_DATA_DIR=/duong-dan-luu-data
APP_LIVE_REFRESH_MS=3000
APP_CACHE_TTL_SECONDS=2.5
APP_MAX_CACHE_ENTRIES=240
COURSE_WEB_URL=https://duong-dan-web-hoc-lieu
```

`APP_DATA_DIR` nen tro den dia persistent disk khi deploy. Neu khong dat, app tao thu muc `data/` canh `app.py`.

## Deploy bang Docker

```sh
docker build -t lop-hoc-ai .
docker run --rm -p 8501:8501 \
  -e GEMINI_API_KEY="$GEMINI_API_KEY" \
  -e COURSE_WEB_URL="https://duong-dan-web-hoc-lieu" \
  -v "$PWD/data:/app/data" \
  lop-hoc-ai
```

## Tich hop vao web hoc lieu

Thu muc `web/` trong goi san pham co `index.html` da them muc "Lop hoc AI" va `ai-classroom.html`.

- Khi chay local: mo `web/ai-classroom.html`, trang se mac dinh nhung `http://localhost:8501`.
- Khi deploy that: doi link nut/iframe sang URL Streamlit public, hoac mo:

```text
ai-classroom.html?app=https%3A%2F%2Fyour-streamlit-app.example.com
```

## Ghi chu migration

Neu thu muc app co cac file `data_*.csv` cu, lan doc du lieu dau tien se import mot lan vao SQLite va tao marker `data/.csv_migrated_to_sqlite`.
