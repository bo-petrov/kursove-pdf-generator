# За програмистите: първо стартиране и WMS интеграция

Този пакет е готовият генератор за модул „Курсове“. Подавате JSON за курса на
`POST /v1/courses/pdf`, получавате `application/pdf`. PDF оформлението е одобрено.
Не е нужен достъп до ERP или WMS база данни от генератора.

## 1. Вземете версията

Репо: https://github.com/bo-petrov/kursove-pdf-generator (частно; нужен е достъп).
За фиксирана версия използвайте release `v1.1.0` или приложения source ZIP.
ZIP съдържа същия код и може да се използва без GitHub акаунт.

## 2. Проверете PDF без сървър

Нужни са Python 3.12+ и достъп до PyPI при инсталиране. След инсталиране
генерирането работи без интернет. Изпълнете от папката на разархивирания проект.

**Linux/macOS:**

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pip install --no-deps .
.venv/bin/kursove-pdf examples/course-six-orders.json course.pdf
```

**Windows PowerShell:**

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -m pip install --no-deps .
.\.venv\Scripts\kursove-pdf.exe examples/course-six-orders.json course.pdf
```

Отворете `course.pdf`. Примерът е с 6 нареждания в 3 клиентски групи на един A4 лист.
Другият пример, `examples/course-twelve-orders.json`, показва продължение.

## 3. Стартирайте HTTP услугата

За Docker/Compose: точните команди са в [README](README.md#стартиране-с-docker).
Алтернативно използвайте вече инсталирания Python пакет:

**Linux/macOS:**

```sh
export KURSOVE_API_TOKEN="$(.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(32))')"
.venv/bin/kursove-pdf-serve
```

**Windows PowerShell:**

```powershell
$env:KURSOVE_API_TOKEN = (& .\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(32))")
.\.venv\Scripts\kursove-pdf-serve.exe
```

Пазете избрания токен в backend конфигурацията и използвайте същата стойност
при заявката. По подразбиране услугата слуша на `127.0.0.1:8080`.
`GET /healthz` трябва да върне `{"ok":true,"version":"1.1.0"}`.
Сървърът остава на преден план; Ctrl+C го спира. За постоянна работа използвайте
Compose или service manager в целевата среда.

## 4. Свържете WMS

- Входните полета и правилата: [docs/API.md](docs/API.md).
- Машинно четим договор и примерна заявка: [docs/openapi.json](docs/openapi.json).
- HTTP клиентски пример и поведение при грешка: [docs/INTEGRATION.md](docs/INTEGRATION.md).
- Основни данни за старт: [examples/course-six-orders.json](examples/course-six-orders.json).

WMS трябва да извика генератора след създаване или редакция на курс, да запази
получения PDF към актуалната версия и да го предостави чрез бутона „Печат“.
Не записвайте JSON грешка като PDF и не показвайте стар файл като актуален.
`orders` остава плосък масив в реда на маршрута. Препоръчително подавайте
`client_id`; генераторът групира само съседни записи за един клиент.
`product_count` е брой позиции, а QR кодира буквалното ID на курса.

## Приемане в целевата среда

Проверете един реален курс с няколко нареждания за един клиент, промяна на реда
и повторно генериране, дълъг адрес, сканиране на QR и печат на A4 при 100% размер.
Генераторът не променя WMS статуси; отметката „Доставен“ е само за химикалка.
Изпълнените проверки са в [docs/VERIFICATION.md](docs/VERIFICATION.md).
