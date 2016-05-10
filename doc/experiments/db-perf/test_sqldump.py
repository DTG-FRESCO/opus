#! /usr/bin/env python2.7
# -*- coding: utf-8 -*-

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

import os

from peewee import SqliteDatabase, Model, CharField
import timer

db = SqliteDatabase("testdumpexample.db")

track = timer.track("sqldump")


class MsgFields(object):
    MSG_TYPE = 1

    # Optional fields
    FUNC_NAME = 2
    FILE_NAME = 3
    FILE_DESC = 4
    PID = 5
    FILE_MODE = 6


class BaseModel(Model):
    class Meta:
        database = db


class Msg(BaseModel):
    type = CharField()
    func_name = CharField(null=True)
    file_name = CharField(null=True)
    file_desc = CharField(null=True)
    pid = CharField(index=True)
    file_mode = CharField(null=True)


@track
def process_msg(msg):
    with db.transaction():
        cur = Msg(type=msg[MsgFields.MSG_TYPE],
                  pid=msg[MsgFields.PID])
        for key in msg:
            if key == MsgFields.FUNC_NAME:
                cur.func_name = msg[key]
                continue
            elif key == MsgFields.FILE_NAME:
                cur.file_name = msg[key]
                continue
            elif key == MsgFields.FILE_DESC:
                cur.file_desc = msg[key]
                continue
            elif key == MsgFields.FILE_MODE:
                cur.file_mode = msg[key]
        cur.save()


def setup():
    db.connect()
#    db.execute_sql('PRAGMA synchronous=OFF')
#    db.execute_sql('PRAGMA journal_mode=MEMORY')
    db.create_tables([Msg])


def teardown():
    db.close()
    os.unlink("testdumpexample.db")
