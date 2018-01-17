IPMT
====

.. image:: https://img.shields.io/pypi/v/ipmt.svg
    :target: https://pypi.python.org/pypi/ipmt

.. image:: https://img.shields.io/travis/inplat/ipmt.svg
    :target: https://travis-ci.org/inplat/ipmt

.. image:: https://codecov.io/gh/inplat/ipmt/branch/master/graph/badge.svg
    :target: https://codecov.io/gh/inplat/ipmt

.. image:: https://readthedocs.org/projects/ipmt/badge/?version=latest
    :target: http://ipmt.readthedocs.io/ru/latest/?badge=latest
    :alt: Documentation Status

.. image:: https://pyup.io/repos/github/inplat/ipmt/shield.svg
    :target: https://pyup.io/repos/github/inplat/ipmt/
    :alt: Updates

Иструмент миграций СУБД PostgreSQL


Возможноти
----------
* Версионирование схемы БД
* Ветвление в версиях
* Управление привилегиями с помощью yaml файлов


Документация
-------------
http://ipmt.readthedocs.io/ru/latest/


Установка
---------
Для установки выполните в консоли::

    $ pip install ipmt


Использование
-------------

Выполните в консоли::

    # инициализация репозитория
    ipmt init
    # создание первой версии
    ipmt create baseline
    # отредактируйте файл миграции разместив SQL в
    # первом аргументе db.execute функции up для
    # наката миграции и в аналогичном месте функции
    # down для отката миграции
    vim versions/000001#baseline.py
    # накат версии на указанную БД
    IPMT_DSN=username@hostname/dbname ipmt up
