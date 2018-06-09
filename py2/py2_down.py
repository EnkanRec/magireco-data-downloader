# coding=utf-8
import os
import requests
import json
import urllib
import time
import sqlite3

MASTER_PATH = "https://android.magi-reco.com/magica/resource/download/asset/master/"

CONFIG_JSON = "asset_config.json"

MAIN_JSON = "asset_main.json"
MOVIE_H_JSON = "asset_movie_high.json"
MOVIE_L_JSON = "asset_movie_low.json"
VOICE_JSON = "asset_voice.json"
CHAR_LIST_JSON="asset_char_list.json"
FULLVOICE_JSON="asset_fullvoice.json"

BASE_URL = MASTER_PATH + "resource/"
SAVE_DIR = '/root/magireco_data/'
RESOURCE_DIR = SAVE_DIR + "resource/"
FAILLIST = []

JSON_LIST=[MAIN_JSON, VOICE_JSON, MOVIE_L_JSON, MOVIE_H_JSON, CHAR_LIST_JSON, FULLVOICE_JSON]
DB="db.json"

def get_json(url):
    session = requests.session()
    content = session.get(url).content
    return json.loads(content)

def read_json(name):
    fjson = open(SAVE_DIR + name, 'r')
    data = fjson.read()
    fjson.close()
    return json.loads(data)

def makedir(path):
    p = path.split('/')
    p.pop()
    p = '/'.join(p)
    if not os.path.exists(p):
        os.makedirs(p)

def download(item):
    retry = 3 # 重试次数
    while retry:
        try:
            urllib.request.urlretrieve(MASTER_PATH + item, SAVE_DIR + item)
            return 200 # 如果上面下载失败会抛出异常并忽略本句
        except urllib.error.HTTPError as err:
            if err.code == 403:
                retry -= 1
            elif err.code == 404:
                return 404
    FAILLIST.append(item)
    return 403

def main():
    db={}
    try:
        db=read_json(DB)
    except:
        pass
    flag = 1
    if os.path.exists(SAVE_DIR + CONFIG_JSON):
        print('[*] Checking update ...')
        remote = get_json(MASTER_PATH + CONFIG_JSON)
        local = read_json(CONFIG_JSON)
        if local['version'] == remote['version']:
            print('[*] Asset up to date')
            flag = 0
    if flag:
        print('[*] Updating asset lists ...')
        for item in ([CONFIG_JSON] + JSON_LIST):
            print('[-] Updating list %s ...' % item)
            download(item)
    #for fjson in [MAIN_JSON, VOICE_JSON, MOVIE_H_JSON]:
    #for fjson in [MOVIE_L_JSON]:
    for fjson in JSON_LIST:
        print('[*] Loading %s ...' % fjson)
        lst = read_json(fjson)
        print('[-] Found %d items' % len(lst))
        cnt = 0
        for p in lst:
            cnt += 1
            #if os.path.exists(RESOURCE_DIR + p['path']):
                # Check md5/ Check in db
            #    print('[@] Found %s aleady exists, count %d/%d ' % (p['path'], cnt, len(lst)))
            #    continue
            if (fjson+RESOURCE_DIR + p['path']) in db and db[fjson+RESOURCE_DIR + p['path']] == p['md5']:
                print('[@] Found %s aleady exists, count %d/%d ' % (p['path'], cnt, len(lst)))
                continue
            print('[@] Downloading %s, count %d/%d ' % (p['path'], cnt, len(lst)), end='')
            makedir(RESOURCE_DIR + p['path'])
            # cntp = 1
            if len(p['file_list']) > 1 or p['file_list'][0]['url'] != p['path']:
                #fout = open(RESOURCE_DIR + p['path'], 'wb')
                for part in p['file_list']:
                    # print('%s' % (BASE_URL + part['url']))
                    #print('.', end='')
                    # print('[ ] Downloading %s, part %d/%d' % (part['url'], cntp, len(p['file_list'])))
                    # cntp += 1
                    makedir(RESOURCE_DIR + part['url'])
                    # urllib.request.urlretrieve(BASE_URL + part['url'], RESOURCE_DIR + part['url'])
                    download("resource/" + part['url'])
                    #pout = open(RESOURCE_DIR + part['url'], 'rb')
                    #fout.write(pout.read(part['size']))
                    #pout.close()
                #fout.close()
            else:
                download("resource/" + p['path'])
            db[fjson+RESOURCE_DIR + p['path']] = p['md5']
            print()

    f=open(SAVE_DIR + DB,"w")
    f.write(json.dumps(db, ensure_ascii=False, sort_keys=True))
    f.close()
    if len(FAILLIST) > 0:
        fout = open(SAVE_DIR + 'fail.log', 'w')
        fout.writelines("Log time: " + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()) + "\n")
        for item in FAILLIST:
            fout.writelines(item + "\n")
        fout.close()

if __name__ == '__main__':
    main()
