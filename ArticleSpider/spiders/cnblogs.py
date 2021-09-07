import re
import json
from urllib.parse import urljoin

import scrapy

from ArticleSpider.items import CnblogsArticleItem
from ArticleSpider.utils import common


class CnblogsSpider(scrapy.Spider):
    name = 'cnblogs'
    allowed_domains = ['news.cnblogs.com']
    start_urls = ['https://news.cnblogs.com/']
    custom_settings = {
        "COOKIES_ENABLED": True
    }

    def start_requests(self):
        # 入口可以模拟登录拿到cookie
        import undetected_chromedriver.v2 as uc
        browser = uc.Chrome()
        browser.get("https://account.cnblogs.com/signin")
        input("回车继续：")
        cookies = browser.get_cookies()
        cookie_dict = {}
        for cookie in cookies:
            cookie_dict[cookie['name']] = cookie['value']

        for url in self.start_urls:
            # 将cookie交给scrapy
            headers = {
                "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.63 Safari/537.36"
            }
            yield scrapy.Request(url, cookies=cookie_dict, headers=headers, dont_filter=True)

    def parse(self, response):
        """
        1. 获取新闻列表页中的新闻url并交给scrapy进行下载后调用相应的解析方法
        2. 获取下一页的url并且交给scrapy下载，下载完成后交给parse进行根进
        """
        post_nodes = response.xpath("//div[@id='news_list']//div[@class='news_block']")
        for post_node in post_nodes:
            image_url = post_node.xpath(".//div[@class='entry_summary']/a/img/@src").extract_first()
            if image_url.startswith("//"):
                image_url = "https:" + image_url
            post_url = post_node.xpath(".//h2/a/@href").extract_first()

            yield scrapy.Request(url=urljoin(response.url, post_url), meta={"front_image_url": image_url}, callback=self.parse_detail)

        # 提取下一页
        next_url = response.xpath("//a[contains(text(), 'Next >')]/@href").extract_first()
        yield scrapy.Request(url=urljoin(response.url, next_url), callback=self.parse)

    def parse_detail(self, response):
        """
        解析详情页数据
        """
        # 使用正则表达式匹配详情页id
        match_re = re.match(".*?(\d+)", response.url)
        # 判断是否是详情页
        if match_re:
            post_id = match_re.group(1)
            # 实例化对象
            article_item = CnblogsArticleItem()
            title = response.xpath("//div[@id='news_title']/a/text()").extract_first()

            create_date = response.xpath("//div[@id='news_info']/span[@class='time']/text()").extract_first()
            match_re = re.match(".*?(\d+.*)", create_date)
            if match_re:
                create_date = match_re.group(1)

            content = response.xpath("//div[@id='news_content']").extract()[0]
            tag_list = response.xpath("//div[@class='news_tags']/a/text()").extract()
            tags = '，'.join(tag_list)


            article_item["title"] = title
            article_item["create_date"] = create_date
            article_item["content"] = content
            article_item["tags"] = tags
            article_item["url"] = response.url
            if response.meta.get("front_image_url", ""):
                article_item["front_image_url"] = [response.meta.get("front_image_url", "")]
            else:
                article_item["front_image_url"] = []

            yield scrapy.Request(url=urljoin(response.url, "/NewsAjax/GetAjaxNewsInfo?contentId={}".format(post_id)),
                                 meta={"article_item": article_item}, callback=self.parse_nums)

    def parse_nums(self, response):
        j_data = json.loads(response.text)
        article_item = response.meta.get("article_item", "")

        praise_nums = j_data["DiggCount"]
        fav_nums = j_data["TotalView"]
        comment_nums = j_data["CommentCount"]

        article_item["praise_nums"] = praise_nums
        article_item["fav_nums"] = fav_nums
        article_item["comment_nums"] = comment_nums
        article_item["url_object_id"] = common.get_md5(article_item["url"])

        yield article_item
