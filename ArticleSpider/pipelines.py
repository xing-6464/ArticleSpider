# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
import codecs
import json


from itemadapter import ItemAdapter
from scrapy.pipelines.images import ImagesPipeline
from scrapy.exporters import JsonItemExporter
from twisted.enterprise import adbapi
import MySQLdb

class ArticlespiderPipeline:
    def process_item(self, item, spider):
        return item


class MysqlPiplines:
    # 同步存储入mysql
    def __init__(self):
        self.conn = MySQLdb.connect("127.0.0.1", 'root', 'root', 'article_spider', charset="utf-8", use_unicode=True)
        self.cursor = self.conn.cursor()

    def process_item(self, item, spider):
        insert_sql = """
            insert into cnblogs_article(title, url, url_object_id, front_image_path, front_image_url, parise_nums, comment_nums, fav_nums, tags, content, create_date)
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ON DUPLDATE url_object_id=VALUE(url_object_id)
        """
        params = list()
        params.append(item.get("title", ""))
        params.append(item.get("url", ""))
        params.append(item.get("url_object_id", ""))
        params.append(item.get("front_image_path", ""))
        front_image_list = ",".join(item.get("front_image_url", []))
        params.append(front_image_list)
        params.append(item.get("parise_nums", 0))
        params.append(item.get("comment_nums", 0))
        params.append(item.get("fav_nums", 0))
        params.append(item.get("tags", ""))
        params.append(item.get("content", ""))
        params.append(item.get("create_date", "1970-07-01"))
        self.cursor.execute(insert_sql, tuple(params))
        self.conn.commit()

        return item


class MysqlTwistedPipline(object):
    # 异步存储入mysql
    def __init__(self, dbpool):
        self.dbpool = dbpool

    @classmethod
    def from_settings(cls, settings):
        dbparms = dict(
            host = settings["MYSQL_HOST"],
            db = settings["MYSQL_DBNAME"],
            user = settings["MYSQL_USER"],
            passwd = settings["MYSQL_PASSWORD"],
            charset='utf8',
            cursorclass=MySQLdb.cursors.DictCursor,
            use_unicode=True,
        )
        dbpool = adbapi.ConnectionPool("MySQLdb", **dbparms)

        return cls(dbpool)

    def process_item(self, item, spider):
        #使用twisted将mysql插入变成异步执行
        query = self.dbpool.runInteraction(self.do_insert, item)
        query.addErrback(self.handle_error, item, spider) #处理异常
        return item

    def handle_error(self, failure, item, spider):
        #处理异步插入的异常
        print (failure)

    def do_insert(self, cursor, item):
        #执行具体的插入
        #根据不同的item 构建不同的sql语句并插入到mysql中
        insert_sql = """
                    insert into cnblogs_article(title, url, url_object_id, front_image_path, front_image_url, parise_nums, comment_nums, fav_nums, tags, content, create_date)
                    values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ON DUPLDATE url_object_id=VALUE(url_object_id)
                """
        params = list()
        params.append(item.get("title", ""))
        params.append(item.get("url", ""))
        params.append(item.get("url_object_id", ""))
        params.append(item.get("front_image_path", ""))
        front_image_list = ",".join(item.get("front_image_url", []))
        params.append(front_image_list)
        params.append(item.get("parise_nums", 0))
        params.append(item.get("comment_nums", 0))
        params.append(item.get("fav_nums", 0))
        params.append(item.get("tags", ""))
        params.append(item.get("content", ""))
        params.append(item.get("create_date", "1970-07-01"))

        cursor.execute(insert_sql, tuple(params))


class JsonWithEncodingPipeline:
    # 自定义json文件的导出
    def __init__(self):
        self.file = codecs.open("article.json", "a", encoding="utf-8")

    def process_item(self, item, spider):
        lines = json.dumps(dict(item), ensure_ascii=False) + "\n"
        self.file.write(lines)
        return item

    def spider_closed(self, spider):
        self.file.close()


# class JsonExporterPipline:
#     # scrapy框架定义json文件方法，的导出
#     def __int__(self):
#         self.file = open("articleexport.json", 'wb')
#         self.exporter = JsonItemExporter(self.file, encoding="utf-8", ensure_ascii=False)
#         self.exporter.start_exporting()
#
#     def process_item(self, item, spider):
#         self.exporter.export_item(item)
#         return item
#
#     def spider_closed(self, spider):
#         self.exporter.finish_exporting()
#         self.file.close()


class ArticleImagePipeline(ImagesPipeline):
    # 下载图片处理
    def item_completed(self, results, item, info):
        if "front_image_url" in item:
            image_file_path = ""
            for ok, value in results:
                image_file_path = value["path"]

            item["front_image_path"] = image_file_path

        return item