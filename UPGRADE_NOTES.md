# Ghi chu nang cap hieu nang

## Huong nghien cuu va quyet dinh

1. Giu Streamlit vi app hien co da tach ro hai vai tro: hoc vien submit-only, giang vien xem live dashboard.
2. Thay CSV append/read bang SQLite de giam loi khi nhieu hoc vien gui cung luc va tranh viec doc lai file CSV lien tuc.
3. Bat SQLite WAL de doc va ghi co the dien ra dong thoi tot hon trong mot lop dang live.
4. Dung `st.cache_data` co `ttl` va `max_entries` cho cac truy van dashboard cua giang vien.
5. Giam live refresh mac dinh cua giang vien tu 1.5s xuong 3s, van cho cau hinh qua `APP_LIVE_REFRESH_MS`.
6. Gom du lieu dong vao `APP_DATA_DIR` de deploy co persistent disk, tranh mat du lieu khi container restart.
7. Tich hop voi web hoc lieu bang trang `web/ai-classroom.html`, nhung app Streamlit qua URL rieng.

## Nguon tham khao

- Streamlit caching: https://docs.streamlit.io/develop/concepts/architecture/caching
- Streamlit configuration: https://docs.streamlit.io/develop/concepts/configuration/options
- SQLite WAL: https://www.sqlite.org/wal.html
