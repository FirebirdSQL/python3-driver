.. module:: firebird.driver.core
    :synopsis: Main Firebird driver code

====================
firebird.driver.core
====================

This is the main code module of the Firebird driver.

Constants and variables
=======================

Translation dictionaries
------------------------

.. autodata:: CHARSET_MAP
   :annotation:

Context managers
================

transaction
-----------
.. autofunction:: transaction

Functions
=========

connect
-------

.. autofunction:: connect

create_database
---------------

.. autofunction:: create_database

connect_server
--------------

.. autofunction:: connect_server

Classes
=======

Connection
----------
.. autoclass:: Connection

InfoProvider
------------
.. autoclass:: InfoProvider

DatabaseInfoProvider
--------------------
.. autoclass:: DatabaseInfoProvider

TransactionManager
------------------
.. autoclass:: TransactionManager

DistributedTransactionManager
-----------------------------
.. autoclass:: DistributedTransactionManager

Statement
---------
.. autoclass:: Statement

Cursor
------
.. autoclass:: Cursor

Server
------
.. autoclass:: Server

EventCollector
--------------
.. autoclass:: EventCollector

EventBlock
----------
.. autoclass:: EventBlock

BlobReader
----------
.. autoclass:: BlobReader


