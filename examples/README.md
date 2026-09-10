# Примерни данни

Всички JSON и PDF примери в тази папка са демонстрационни: измислени клиенти,
получатели и адреси, маскирани телефони. Не представляват реална доставка.

- course-six-orders.json → pdf/course-six-orders.pdf (1 страница, 3 клиента с 3+2+1 нареждания).
- course-twelve-orders.json → pdf/course-twelve-orders.pdf (2 страници, 3 клиента с 9+2+1 нареждания; първата група продължава).

Генериране след инсталиране на пакета:

```sh
kursove-pdf examples/course-six-orders.json examples/pdf/course-six-orders.pdf --sample
kursove-pdf examples/course-twelve-orders.json examples/pdf/course-twelve-orders.pdf --sample
```

Само `--sample` добавя надпис „ОБРАЗЕЦ“. HTTP услугата връща нормален PDF.
