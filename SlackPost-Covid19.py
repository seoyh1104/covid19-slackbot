# -------------------------------------------------------------------------------------------------#
# SlackPost-Covid19.py: Covid19 Data Collection and Send a message to Slack                        #
# -------------------------------------------------------------------------------------------------#
#  AUTHOR: Yuhui.Seo        2022/12/09                                                             #
# --< CHANGE HISTORY >-----------------------------------------------------------------------------#
#          Yuhui.Seo        2022/12/09 #001(Add config file)                                       #
#          Yuhui.Seo        2022/12/29 #002(Change layout, Use QuickChart)                         #
#          Yuhui.Seo        2023/02/27 #003(Add date flag and remove_duplicates fuction)           #
#          Yuhui.Seo        2023/03/03 #004(Change common function and Apply Pyrint)               #
#          Yuhui.Seo        2023/03/10 #005(Change class inheritance)                              #
# --< Version >------------------------------------------------------------------------------------#
#          Python version 3.11.0 (Requires python version 3.10 or higher.)                         #
# -------------------------------------------------------------------------------------------------#
# Main process                                                                                     #
# -------------------------------------------------------------------------------------------------#
from urllib import request as r, parse
from urllib.error import URLError
from datetime import date, datetime, timedelta
import os
import json
import socket
import configparser
import xml.etree.ElementTree as ET
import matplotlib.pyplot as plt      # requires: pip install matplotlib
import matplotlib.font_manager as fm
from slack_sdk import WebClient      # requires: pip install slack_sdk
from slack_sdk.errors import SlackApiError


class SystemInfo:
    def __init__(self):
        pass

    def system_info(self):
        hostname = socket.gethostname()  # PC명
        # ip = socket.gethostbyname(hostname) #IP주소
        return hostname

    def set_relative_file_path(self):
        program_directory = os.path.dirname(os.path.abspath(__file__))
        os.chdir(program_directory)


class CommonFunc:
    def str_to_int(self, number_str):
        number = int(number_str)
        return format(number, ',')

    def extract_filename(self, file_path):
        filename = file_path.split('/')[-1]
        return filename

    def get_formatted_datetime(self, date_time, fmt):
        formats = {
            1: '%Y%m%d',                   # yyyyMMdd
            2: '%Y-%m-%d',                 # yyyy-MM-dd
            3: '%Y-%m-%d %H:%M:%S',        # yyyy-MM-dd HH:mm:ss
            4: '%Y%m%d%H%M%S',             # yyyyMMddHHmmss
            5: '%Y년 %m월 %d일',            # yyyy년 MM월 dd일
            6: '%Y년%m월%d일 %H시%M분%S초',  # yyyy년MM월dd일 HH시mm분ss초
            7: '%Y/%m/%d',                 # YY/MM/dd/
        }
        fmt_str = formats.get(fmt, '%Y%m%d%H%M%S')
        if isinstance(date_time, str):
            date_time = datetime.strptime(date_time, '%Y%m%d%H%M%S')
        return date_time.strftime(fmt_str)


class ReadConfig:
    def __init__(self, sys_info):
        SystemInfo.set_relative_file_path(sys_info)
        self.conf_file = 'config.ini'

    def load_config(self):
        if not os.path.exists(self.conf_file):
            raise FileNotFoundError(f"{self.conf_file} file does not exist.")
        else:
            config = configparser.ConfigParser()
            config.read(self.conf_file, encoding='utf-8')
            print(f"Load Config : {self.conf_file}")
            return config


class FileAPI(CommonFunc):
    def __init__(self, sys_info, config, covid19):
        self.sys_info = sys_info
        self.covid19 = covid19
        config = config['FILES']
        self.dir_download = config['dir_download']
        self.dir_result = config['dir_result']
        # self.dir_chart = config['dir_chart']
        self.file_name = config['file_name']
        self.file_list = []
        self.result_file_name = config['result_file_name']
        self.exists_dir()

    def exists_dir(self):
        self.mkdir(self.dir_download)
        self.mkdir(self.dir_result)
        # self.mkdir(self.dir_chart)

    def mkdir(self, directory):
        if not os.path.exists(directory):
            os.mkdir(directory)

    def check_result(self):
        file_path = self.set_txt_file_path()
        if not os.path.isfile(file_path):
            return True
        else:
            print('Result file exists. : ' + file_path)
            return False

    def set_date(self):
        start_date = date.today() - timedelta(days=12)  # 기간 설정
        end_date = date.today()

        while start_date <= end_date:
            file_path = self.set_filepath(start_date)
            if self.find_xml_file(start_date, file_path):
                self.file_list.append(file_path)
            start_date += timedelta(days=1)

        return self.file_list

    def set_filepath(self, date_time):
        date_time = self.get_formatted_datetime(date_time, 1)
        file_name = date_time + '_' + self.file_name
        file_path = os.path.join(self.dir_download, file_name)
        return file_path

    def set_txt_file_path(self):
        dates = self.get_formatted_datetime(date.today(), 1)
        file_name = dates + '_' + self.result_file_name
        file_path = os.path.join(self.dir_result, file_name)
        return file_path

    def find_xml_file(self, dates, file_path):
        if not os.path.isfile(file_path):
            response_body = Covid19API.http_get(self.covid19, dates)
            if response_body:
                self.save_file(file_path, response_body, 'Xml')
                return True
            else:
                return False
        else:
            print('Xml file exists. : ' + file_path)
            return True

    def find_txt_file(self):
        file_path = self.set_txt_file_path()
        if not os.path.isfile(file_path):
            text_byte = 'ok'.encode('utf-8')
            self.save_file(file_path, text_byte, 'Result')
        else:
            print(f"Result file exists. : ' {file_path}")

    def save_file(self, file_path, data, text):
        file = open(file_path, 'wb')
        file.write(data)
        file.close()
        print(f"{text} file saved successfully. : {file_path}")


class Covid19API(CommonFunc):
    def __init__(self, sys_info, config):
        config = config['COVID19']
        self.sys_info = sys_info
        self.service_key = config['decoding_key']
        self.url = config['url']

    def set_covid19uri(self, dates):
        params = '?' + parse.urlencode({
            # ✔ 서비스키
            parse.quote_plus('serviceKey'): parse.unquote(self.service_key),
            # ✔ 페이지 번호
            parse.quote_plus('pageNo'): '1',
            # ✔ 한 페이지 결과 수
            parse.quote_plus('numOfRows'): '500',
            # 데이터유형
            parse.quote_plus('apiType'): 'xml',
            # 기준일자
            parse.quote_plus('std_day'): self.get_formatted_datetime(dates, 2)
            # parse.quote_plus('gubun'): '인천', # 시도명
        })
        return params

    def http_get(self, params):
        try:
            request = r.Request(self.url + self.set_covid19uri(params))
            request.get_method = lambda: 'GET'
            response = r.urlopen(request)
            response_body = response.read()
            tree = ET.fromstring(response_body)
            result_code = tree.findtext('header/resultCode')

            if response.status == 200 and result_code == '00' and tree.findtext('body/items/item'):
                # print(response.headers) # Date, Server, Content-Length, Connection, Content-Type
                # print('response.url : ' + response.url) # redirection url
                return response_body
            else:
                return False
                # TODO: 질병관리청에서 일요일과 공휴일 통계를 발표하지 않기로 함에 따라 데이터 취득 불가능
                # 처리 플래그 설정 필요, 이전 날짜의 파일을 리스트에 추가해야함. 다른 방법이 있는지 확인
        except URLError as error:
            print(f"Failed to make request: {error}")
            return False
        except ET.ParseError as error:
            print(f"Failed to parse response: {error}")
            return False


class ReadXmlData(CommonFunc):
    def __init__(self, file_list):
        self.file_list = file_list
        self.today = self.get_formatted_datetime(date.today(), 2)

    def get_root_from_file(self, file):
        tree = ET.parse(file)
        return tree.getroot()

    def get_data(self):
        total_stdday_list = []
        total_incdec_list = []
        data_cnt = {}
        data_dict = {}
        for file in self.file_list:
            root = self.get_root_from_file(file)
            sido = 'Incheon'

            for data in root.findall('body/items/item'):
                if data.findtext('gubunEn') == 'Total':
                    # dict['시도명'] = data.findtext('gubun')
                    # dict['시도명(영문)'] = data.findtext('gubunEn')
                    data_dict['전일대비확진자증감수'] = data.findtext('incDec')
                    # dict['누적격리해제수'] = data.findtext('isolClearCnt') # data값 전부 0
                    # dict['격리중환자수'] = data.findtext('isolIngCnt') # data값 전부 0
                    # dict['10만명당발생율'] = data.findtext('qurRate')
                    # 기준일자 포맷 변경 시
                    # stdDay_str = data.findtext('stdDay')
                    # dict['기준일자'] = stdDay_str[-5:].replace('-', '/')
                    data_dict['기준일자'] = data.findtext('stdDay')
                    total_stdday_list.append(data_dict['기준일자'])
                    total_incdec_list.append(data_dict['전일대비확진자증감수'])
                if data.findtext('stdDay') == self.today and data.findtext('gubunEn') == 'Total':
                    data_cnt['누적확진자수'] = self.str_to_int(
                        data.findtext('defCnt'))
                    data_cnt['전일대비확진자증감수'] = self.str_to_int(
                        data.findtext('incDec'))
                    data_cnt['지역발생수'] = self.str_to_int(
                        data.findtext('localOccCnt'))
                    data_cnt['해외유입수'] = self.str_to_int(
                        data.findtext('overFlowCnt'))
                    data_cnt['사망자수'] = self.str_to_int(
                        data.findtext('deathCnt'))
                if data.findtext('stdDay') == self.today and data.findtext('gubunEn') == sido:
                    data_cnt[sido] = self.str_to_int(
                        data.findtext('incDec'))

        unique_stdday, unique_incdec = self.remove_duplicates(
            total_stdday_list, total_incdec_list)
        return unique_stdday, unique_incdec, data_cnt

    def remove_duplicates(self, total_stdday_list, total_incdec_list):
        # 중복되지 않은 stdDay 리스트와 그에 맞는 incdec 리스트를 저장할 변수 초기화
        unique_stdday_list = []
        unique_incdec_list = []

        # 중복을 제거하면서 unique_stdday_list와 unique_incdec_list에 값을 추가
        for i, total_stdday in enumerate(total_stdday_list):
            if i == 0 or total_stdday != total_stdday_list[i-1]:
                unique_stdday_list.append(total_stdday)
                unique_incdec_list.append(total_incdec_list[i])

        return unique_stdday_list, unique_incdec_list


class ChartAPI(CommonFunc):
    def __init__(self, config):
        # matplotlib 한글깨짐 방지
        font_list = [font.name for font in fm.fontManager.ttflist]
        if 'Malgun Gothic' in font_list:
            plt.rcParams['font.family'] = 'Malgun Gothic'  # Windows OS
        elif 'NanumGothic' in font_list:
            plt.rcParams['font.family'] = 'NanumGothic'
        else:
            plt.rcParams['font.family'] = 'AppleGothic'  # Mac OS
        plt.rcParams['axes.unicode_minus'] = False  # (-) 부호 깨짐 현상 방지

        self.dir_chart = config.get('FILES', 'dir_chart')
        self.chart_name = config.get('FILES', 'chart_name')
        self.today = self.get_formatted_datetime(date.today(), 5)
        self.chart_dt = self.get_formatted_datetime(datetime.today(), 4)

    def create_chart(self, total_stdday_list, total_incdec_list):
        idx_list = list(range(len(total_stdday_list)))
        inc_dec = list(map(int, total_incdec_list))

        plt.figure(figsize=(10, 6))  # 그래프 크기 지정
        plt.suptitle('한국 코로나19 감염 추이', fontsize=16, color='black')
        plt.title('기준일자 : ' + self.today, loc='right',
                fontsize=12, color='gray')
        plt.xlabel('기준일자', fontsize=13)
        plt.ylabel('확진자수(명)', fontsize=13)

        # 꺾은 선 그래프 생성
        plt.plot(idx_list, inc_dec,
                linewidth=3, color='hotpink', label='확진자 수 추이',  # 선 스타일 지정, 범례 추가
                # 표식 추가, 표식 스타일 지정
                marker='o', markersize=6, markeredgecolor='hotpink', markerfacecolor='white')

        # 범례 표시 및 위치 지정
        plt.legend(loc='best')

        # x축 설정
        plt.xticks(idx_list, labels=total_stdday_list,
                   rotation=35)  # rotation:각도

        # 그래프 값 표시
        for i, height in enumerate(inc_dec):
            plt.text(idx_list[i], height, format(height, ','),
                     ha='center', va='bottom', size=11, color='black')

        file_name = self.chart_name + '_' + self.chart_dt + '.png'
        file_path = os.path.join(self.dir_chart, file_name)
        plt.savefig(file_path, dpi=100)
        # plt.show()

        return file_path


class I18nAPI:
    def __init__(self):
        self.i18n = {
            "en": {
                "notification": "Today''s COVID-19 Notification in S.Korea",
                "title": "COVID-19 Statistics",
                "block_section_one_title": ":one: New Cases (Subtotal) : ",
                "block_section_two_title": ":two: Daily Trend",
                "attach_one_title": ":one: Daily New Cases",
                "attach_one_field_one": "Subtotal (A+B)",
                "attach_one_field_two": "Domestic (A)",
                "attach_one_field_three": "Inflow (B)",
                "attach_one_field_four": "Incheon",
                "attach_one_footer": "<http://ncov.kdca.go.kr/en/|KDCA(English)>",
                "attach_two_title": ":two: Chart",
                "attach_two_field_one": "Confirmed",
                "attach_two_field_two": "Death",
                "attach_two_footer": "<http://ncov.kdca.go.kr/en/|KDCA(English)>",
                "plot_title": "Daily Trend of COVID-19, Republic of Korea",
                "plot_data_one": "Confirmed",
                "plot_xlabel": "Date",
                "plot_ylabel": "Cases"
            },
            "ko": {
                "notification": "오늘의 코로나19 알림",
                "title": "코로나19 통계정보",
                "block_section_one_title": ":one: 추가확진 (소계) : ",
                "block_section_two_title": ":two: 일자별 추이",
                "attach_one_title": ":one: 추가확진",
                "attach_one_field_one": "소계 (A+B)",
                "attach_one_field_two": "국내 (A)",
                "attach_one_field_three": "해외유입 (B)",
                "attach_one_field_four": "인천",
                "attach_one_footer": "<http://ncov.kdca.go.kr/|KDCA(Korean)>",
                "attach_two_title": ":two: 차트",
                "attach_two_field_one": "누적확진",
                "attach_two_field_two": "사망",
                "attach_two_footer": "<http://ncov.kdca.go.kr/|KDCA(Korean)>",
                "plot_title": "한국의 코로나19 감염 추이",
                "plot_data_one": "확진",
                "plot_xlabel": "일자",
                "plot_ylabel": "건수"
            },
            "ja": {
                "notification": "本日のコロナ19のお知らせ(韓国)",
                "title": "コロナ19の統計情報",
                "block_section_one_title": ":one: 追加確診 (小計) : ",
                "block_section_two_title": ":two: 日付別推移",
                "attach_one_title": ":one: 追加確診",
                "attach_one_field_one": "小計 (A+B)",
                "attach_one_field_two": "韓国国内 (A)",
                "attach_one_field_three": "海外流入 (B)",
                "attach_one_field_four": "仁川",
                "attach_one_footer": "<http://ncov.kdca.go.kr/en/|KDCA(English)>",
                "attach_two_title": ":two: チャート",
                "attach_two_field_one": "累積確診",
                "attach_two_field_two": "死亡",
                "attach_two_footer": "<http://ncov.kdca.go.kr/en/|KDCA(English)>",
                "plot_title": "韓国のコロナ19感染推移",
                "plot_data_one": "確診",
                "plot_xlabel": "日付",
                "plot_ylabel": "件数"
            }
        }

    def set_i18n(self, lang):
        lang = self.i18n.get(lang)
        return lang


class SlackAPI(CommonFunc):
    def __init__(self, sys_info, config):
        token = config.get('SLACK', 'bot_token')
        # 슬랙 클라이언트 인스턴스 생성
        self.client = WebClient(token)
        self.channel_id = config.get('SLACK', 'channel_id')
        self.hostname = sys_info.system_info()
        self.datetime = self.get_formatted_datetime(date.today(), 2)
        self.payload = {
            "IconUrl": config.get('SLACK', 'icon_url')
        }
        self.chart_labels = []
        self.chart_data = []

    def set_payload(self, total_stdday_list, total_incdec_list, cnt_data):
        self.payload.update(cnt_data)
        self.chart_labels = total_stdday_list
        self.chart_data = total_incdec_list

    def post_message(self, text):
        chart = {
            "type": "bar",
            "data": {
                "labels": self.chart_labels,
                "datasets": [
                    {
                        "type": "line",
                        "label": text.get('plot_data_one'),
                        "borderColor": "rgb(255, 99, 132)",
                        "backgroundColor": "rgba(255, 99, 132, 0.5)",
                        "fill": "false",
                        "data": self.chart_data
                    }
                ]
            },
            "options": {
                "title": {
                    "display": "true",
                    "text": text.get('plot_title'),
                },
                "scales": {
                    "xAxes": [
                        {
                            "scaleLabel": {
                                "display": "true",
                                "labelString": text.get('plot_xlabel')
                            }
                        }
                    ],
                    "yAxes": [
                        {
                            "ticks": {
                                "beginAtZero": "true"
                            },
                            "scaleLabel": {
                                "display": "true",
                                "labelString": text.get('plot_ylabel')
                            }
                        }
                    ]
                }
            }
        }
        chart_url = 'https://quickchart.io/chart?bkg=%23ffffff&c='
        chart_url += parse.urlencode({'data': json.dumps(chart)})

        try:
            self.client.chat_postMessage(
                channel=self.channel_id,
                text=text.get('notification'),
                blocks=[
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": text.get('title')
                        }
                    },
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "plain_text",
                                "text": self.hostname + ", " + self.datetime
                            }
                        ]
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": text.get('block_section_one_title')
                            + self.payload.get('전일대비확진자증감수')
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": text.get('block_section_two_title')
                        }
                    },
                    {
                        "type": "divider"
                    }
                ],
                attachments=[
                    {
                        "fields": [
                            {
                                "short": True,
                                "title": text.get('attach_one_field_one'),
                                "value": self.payload.get('전일대비확진자증감수')
                            },
                            {
                                "short": True,
                                "title": text.get('attach_one_field_two'),
                                "value": self.payload.get('지역발생수')
                            },
                            {
                                "short": True,
                                "title": text.get('attach_one_field_three'),
                                "value": self.payload.get('해외유입수')
                            },
                            {
                                "short": True,
                                "title": text.get('attach_one_field_four'),
                                "value": self.payload.get('Incheon')
                            },
                            {
                                "short": True,
                                "title": text.get('attach_two_field_one'),
                                "value": self.payload.get('누적확진자수')
                            },
                            {
                                "short": True,
                                "title": text.get('attach_two_field_two'),
                                "value": self.payload.get('사망자수')
                            }
                        ],
                        "title": text.get('attach_one_title'),
                        "color": "#dddddd",
                        "mrkdwn_in": ["title", "fields"],
                        "footer_icon": self.payload.get('IconUrl'),
                        "footer": text.get('attach_one_footer'),
                        # "ts": create time 정보 없음
                    },
                    {
                        "color": "#dddddd",
                        "title": text.get('attach_two_title'),
                        "image_url": chart_url
                    }
                ]
            )
        except SlackApiError as error:
            print(f"Slack API 오류 발생: {error.response['error']}")


# -------------------------------------------------------------------------------------------------#
# Code Entry                                                                                       #
# -------------------------------------------------------------------------------------------------#


def main():
    sys_info = SystemInfo()
    config = ReadConfig.load_config(ReadConfig(sys_info))
    covid19 = Covid19API(sys_info, config)
    slack = SlackAPI(sys_info, config)
    file = FileAPI(sys_info, config, covid19)

    # 1. Check today's result data and C19 data
    if FileAPI.check_result(file) and Covid19API.http_get(covid19, date.today()):

        # 2. Check all C19 xml exist, Download C19 xml
        file_list = FileAPI.set_date(file)

        # 3. Extract C19 Data from xml file
        total_stdday_list, total_incdec_list, data_cnt = ReadXmlData.get_data(
            ReadXmlData(file_list))

        # Create chart (matplotlib를 사용하여 차트를 새로 만드는 경우)
        # ChartAPI.create_chart(ChartAPI(config), total_stdday_list, total_incdec_list

        # 4. Set the payload
        SlackAPI.set_payload(slack, total_stdday_list,
                            total_incdec_list, data_cnt)

        # 5. Set i18n and post to Slack
        language = ['ko', 'ja', 'en']
        for lang in language:
            text = I18nAPI.set_i18n(I18nAPI(), lang)
            SlackAPI.post_message(slack, text)

        # 6. Save result file
        FileAPI.find_txt_file(file)


if __name__ == "__main__":
    main()
