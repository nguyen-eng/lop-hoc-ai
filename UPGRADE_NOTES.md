# Ghi chu nang cap hieu nang

## Huong nghien cuu va quyet dinh

1. Giu Streamlit vi app hien co da tach ro hai vai tro: hoc vien submit-only, giang vien xem live dashboard.
2. Thay CSV append/read bang SQLite de giam loi khi nhieu hoc vien gui cung luc va tranh viec doc lai file CSV lien tuc.
3. Bat SQLite WAL de doc va ghi co the dien ra dong thoi tot hon trong mot lop dang live.
4. Dung `st.cache_data` co `ttl` va `max_entries` cho cac truy van dashboard cua giang vien.
5. Giam live refresh mac dinh cua giang vien tu 1.5s xuong 3s, van cho cau hinh qua `APP_LIVE_REFRESH_MS`.
6. Gom du lieu dong vao `APP_DATA_DIR` de deploy co persistent disk, tranh mat du lieu khi container restart.
7. Tich hop voi web hoc lieu bang trang `web/ai-classroom.html`, nhung app Streamlit qua URL rieng.
8. Mo rong flashcard trong `web/index.html` tu 120 the co ban len 1.240 the on sau, moi noi dung co 40-46 the.
9. Thiet ke flashcard theo nguyen tac tu `Make It Stick`: truy hoi chu dong, on cach quang, tron kieu cau hoi, tu giai thich, tu tao cau tra loi va nhan phan hoi.
10. Gan noi dung voi tinh huong CAND de hoc vien khong chi hoc thuoc khai niem ma biet dung nguyen ly vao phan tich, ren luyen va cong tac.

## Nguon tham khao

- Streamlit caching: https://docs.streamlit.io/develop/concepts/architecture/caching
- Streamlit configuration: https://docs.streamlit.io/develop/concepts/configuration/options
- SQLite WAL: https://www.sqlite.org/wal.html
- Make It Stick, Harvard University Press: https://www.hup.harvard.edu/books/9780674729018
- Retrieval practice/testing effect: https://en.wikipedia.org/wiki/Testing_effect
- Spaced repetition: https://en.wikipedia.org/wiki/Spaced_repetition
