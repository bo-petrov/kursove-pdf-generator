# kursove-pdf-generator

**Подавате данните за курс → получавате готов PDF.**

За първо стартиране и внедряване започнете от [START_HERE.md](START_HERE.md).

Генератор за модул „Курсове“ в WMS: A4, QR с ID, общи данни и складови
нареждания в подадената поредност. Кирилски шрифтове са включени в пакета.
Версия 1.1.0 групира съседните нареждания за един клиент под обща черна шапка
с празно квадратче „Доставен“ за химикалка. Примерът с 6 нареждания в 3 групи
е един лист; повече отделни клиенти или дълги текстове могат да добавят страници. Няма база данни, външни API или автоматичен печат.

## Стартиране с Docker

```sh
cp .env.example .env
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Запишете генерираната стойност като `KURSOVE_API_TOKEN` в `.env`, после:

```sh
docker compose up --build -d
curl --fail http://127.0.0.1:8080/healthz
```

Услугата слуша на `127.0.0.1:8080`. Използвайте същия токен във WMS backend-а.
Липсващ токен спира стартирането. `.env` не се добавя в Git.

## Първа заявка

В shell задайте `KURSOVE_API_TOKEN` със същата стойност от `.env`.

```sh
curl --fail-with-body \
  -H "Authorization: Bearer $KURSOVE_API_TOKEN" \
  -H "Content-Type: application/json" \
  --data-binary @examples/course-six-orders.json \
  http://127.0.0.1:8080/v1/courses/pdf \
  --output course.pdf
```

При успех тялото е PDF. При неуспех проверете HTTP кода и JSON грешката;
не записвайте грешката като работен PDF. Подробности: [API](docs/API.md).

## Без Docker: Python 3.12+

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.lock
pip install --no-deps .
kursove-pdf examples/course-six-orders.json course.pdf
```

За HTTP: задайте `KURSOVE_API_TOKEN` в средата и стартирайте `kursove-pdf-serve`.
По подразбиране адресът е 127.0.0.1:8080; `KURSOVE_HOST` и `KURSOVE_PORT` го променят.
На Windows активирайте `.venv\Scripts\Activate.ps1` и задайте токена през
`$env:KURSOVE_API_TOKEN`; услугата използва Waitress, а не Flask dev сървъра.

## За програмистите

- [Интеграция в WMS](docs/INTEGRATION.md): автоматично генериране, версии на курса, печат.
- [Договор за данните](docs/API.md) и [OpenAPI](docs/openapi.json).
- [Примерни JSON и PDF файлове](examples/README.md).
- [Проверки и ограничения](docs/VERIFICATION.md).
- [Лицензи на включените шрифтове](THIRD_PARTY_NOTICES.md).

Вход: текстови ID/номера/телефони, дата YYYY-MM-DD, `product_count` = брой позиции.
Незадължителното `client_id` идентифицира клиента за групиране; старите заявки
без него продължават да работят по точно съвпадение на името. Подробните правила
са в [API](docs/API.md). Незадължителни контакти могат да липсват; адресът, клиентът и документите са задължителни.
Валидирането се използва и от HTTP, и от CLI, и от Python `generate_pdf()`.

## Разработка и проверки

```sh
pip install -r requirements-dev.lock
pip install --no-deps -e .
pytest
python tools/smoke_http.py http://127.0.0.1:8080 "$KURSOVE_API_TOKEN"
python -m build
```

Последната HTTP проверка изисква работеща услуга. GitHub workflow проверява
тестовете, Docker build и реална заявка към контейнера след публикуване на repo-то.
Документацията не означава, че този workflow вече е изпълнен.
