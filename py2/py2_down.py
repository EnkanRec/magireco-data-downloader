# coding=utf-8
import os
import json
import time
import sqlite3
import sys
if sys.version_info.major == 2:
    from urllib import urlopen
else:
    from urllib.request import urlopen

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

def read_json(name):
    with open(SAVE_DIR + name, 'r') as f:
        data = f.read()
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
            #if sys.version_info.major == 2:
            #urllib.request.urlretrieve(MASTER_PATH + item, SAVE_DIR + item)
            s = urlopen(MASTER_PATH + item)
            if s.getcode() != 200:
                retry -= 1
                continue
            with open(SAVE_DIR + item, "wb") as f:
                f.write(s.read())
            return 200 # 如果上面下载失败会抛出异常并忽略本句
        except KeyboardInterrupt:
            raise KeyboardInterrupt
        except:
            retry -= 1
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
        local = read_json(CONFIG_JSON)
        remote = json.load(urlopen(MASTER_PATH + CONFIG_JSON))
        if local['version'] == remote['version']:
            print('[*] Asset up to date')
            flag = 0
        else:
            with open(SAVE_DIR + CONFIG_JSON, "wb") as f:
                json.dump(remote, f, indent=4, separators=(', ', ': '))
    else:
        download(CONFIG_JSON)
    if flag:
        print('[*] Updating asset lists ...')
        for item in (JSON_LIST):
            print('[-] Updating list %s ...' % str(item))
            download(item)
    try:
        #for fjson in [MAIN_JSON, VOICE_JSON, MOVIE_H_JSON]:
        #for fjson in [MOVIE_L_JSON]:
        for fjson in JSON_LIST:
            print('[*] Loading %s ...' % str(fjson))
            lst = read_json(fjson)
            print('[-] Found %d items' % len(lst))
            cnt = 0
            for p in lst:
                cnt += 1
                if (fjson+RESOURCE_DIR + p['path']) in db and db[fjson+RESOURCE_DIR + p['path']] == p['md5']:
                    print('[@] Found %s aleady exists, count %d/%d ' % (str(p['path']), cnt, len(lst)))
                    continue
                print('[@] Downloading %s, count %d/%d ' % (str(p['path']), cnt, len(lst)))
                makedir(RESOURCE_DIR + p['path'])
                cntp = 1
                if len(p['file_list']) > 1 or p['file_list'][0]['url'] != p['path']:
                    with open(RESOURCE_DIR + p['path'], 'wb') as fout:
                        for part in p['file_list']:
                            # print('%s' % (BASE_URL + str(part['url'])))
                            print('[ ] Downloading %s, part %d/%d' % (str(part['url']), cntp, len(p['file_list'])))
                            cntp += 1
                            makedir(RESOURCE_DIR + part['url'])
                            download("resource/" + part['url'])
                            with open(RESOURCE_DIR + part['url'], 'rb') as pout:
                                fout.write(pout.read(part['size']))
                else:
                    download("resource/" + p['path'])
                db[fjson+RESOURCE_DIR + p['path']] = p['md5']
    except KeyboardInterrupt:
        pass
    with open(SAVE_DIR + DB,"w") as f:
        f.write(json.dumps(db, ensure_ascii=False, indent=2, sort_keys=True))
    if len(FAILLIST) > 0:
        with open(SAVE_DIR + 'fail.log', 'a') as f:
            f.writelines("Log time: " + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()) + "\n")
            for item in FAILLIST:
                f.writelines(item + "\n")

if __name__ == '__main__':
    main()
