# coding=utf-8
import os
import re
import json
import time
import sqlite3
# import urllib.request as request
import threading

if os.name == 'nt':
	grep = "find"
	NUL = "NUL"
else:
	grep = "grep"
	NUL = "/dev/null"

def makepath(p1, p2):
	for i in p2.split('/'):
		p1 = os.path.join(p1, i)
	return p1

CURL_CONFIG = '' # " --resolve android.magi-reco.com:443:2600:9000:20ab:7200:19:70ed:2780:93a1 -x socks5://127.0.0.1:1080 "
GAME_HOST = "https://android.magi-reco.com/"
MASTER_PATH = GAME_HOST + "magica/resource/download/asset/master/"

CONFIG_JSON = "asset_config.json"

MAIN_JSON = "asset_main.json"
MOVIE_H_JSON = "asset_movie_high.json"
MOVIE_L_JSON = "asset_movie_low.json"
VOICE_JSON = "asset_voice.json"
CHAR_LIST_JSON="asset_char_list.json"
FULLVOICE_JSON="asset_fullvoice.json"
PROLOGUE_VOICE = "asset_prologue_voice.json"
PROLOGUE_MAIM = "asset_prologue_main.json"

# ERROR403 = BASE_URL + "image_web/common/logo/logo.png"
ERROR403 = GAME_HOST
ERRORLEN = 6351
ERRORTAG = '"d35a7bb0529c5095e8da9113c4ca5578"'

BASE_URL = MASTER_PATH + "resource/"
SAVE_DIR = os.path.dirname(os.path.realpath(__file__))
RESOURCE_DIR = makepath(SAVE_DIR, "resource")
JSON_LIST = [MAIN_JSON, VOICE_JSON, MOVIE_H_JSON, CHAR_LIST_JSON, FULLVOICE_JSON, PROLOGUE_VOICE, PROLOGUE_MAIM]
# JSON_LIST = [MOVIE_L_JSON]
FAILLIST = []
db = sqlite3.connect(makepath(SAVE_DIR, 'madomagi.db'))
if not db.execute("SELECT COUNT(*) FROM sqlite_master where type='table' and name='download_asset'").fetchone()[0]:
	db.execute("CREATE TABLE download_asset(path char(128) primary key,md5 char(128))")
if not db.execute("SELECT COUNT(*) FROM sqlite_master where type='table' and name='asset_json'").fetchone()[0]:
	db.execute("CREATE TABLE asset_json(file char(128) primary key,etag char(128))")
dbevent = []

def select_all(table):
	cursor = db.execute("SELECT * FROM " + table)
	res = {}
	for row in cursor:
		res[row[0]] = row[1]
	return res

def update(file, md5, type):
	if type:
		table = 'download_asset'
		key = 'path'
		value = 'md5'
	else:
		table = 'asset_json'
		key = 'file'
		value = 'etag'
	# DELETE *; INSERT
	res = db.execute("SELECT * FROM {} WHERE {} = '{}'".format(table, key, file))
	if len(res.fetchall()):
		db.execute("UPDATE {} SET {} = '{}' WHERE {} = '{}'".format(table, value, md5, key, file))
	else:
		db.execute("INSERT INTO {} ({}, {}) VALUES ('{}', '{}')".format(table, key, value, file, md5))

def md5sum(path):
	with os.popen('md5sum ' + path + ' | cut -d " " -f 1') as f:
		return f.read()[1:-1]

def fsize(path):
	return os.stat(path).st_size

def errorCheck():
	global ERRORTAG, ERRORLEN
	with os.popen('curl -I ' + ERROR403 + CURL_CONFIG + ' 2>' + NUL) as f:
		head = f.read()
	etag = re.search(r'ETag: (.*)\n', head, re.I)[1]
	cl = re.search(r'Content-Length: (.*)\n', head, re.I)[1]
	ERRORTAG = etag
	ERRORLEN = int(cl)

# type 0: json; 1: item; 2: part;
def download(item, type = 0, md5 = ""):
	global FAILLIST, dbevent
	try:
		path = os.path.dirname(makepath(SAVE_DIR, item))
		if not os.access(path, os.F_OK):
			os.makedirs(path)
	except FileExistsError:
		pass
	except:
		raise
	path = makepath(SAVE_DIR, item)
	try:
		with os.popen('curl -v -o "' + path + '" "' + MASTER_PATH + item + '"' + CURL_CONFIG + '--retry 3 2>&1') as f:
			head = f.read()
		lm = re.search(r'Last-Modified: (.*)\n', head, re.I)[1]
		etag = re.search(r'ETag: (.*)\n', head, re.I)[1]
		cl = re.search(r'Content-Length: (.*)\n', head, re.I)[1]
		if etag == ERRORTAG or int(cl) == ERRORLEN:
			# raise InterruptedError
			FAILLIST.append(item)
			return -1
		if type == 0:
			# update(item, etag, False)
			dbevent.append(threading.Thread(target=update, args=(item, etag, False, )))
		else:
			if type == 1:
				# md5 = md5sum(path)
				# update(item, md5, True)
				dbevent.append(threading.Thread(target=update, args=(item, md5, True, )))
		os.system('touch ' + path + ' -d "' + lm + '"')
		return 0
	except KeyboardInterrupt:
		raise KeyboardInterrupt
	except:
		FAILLIST.append(item)
	return -1

def download_p(i):
	global dbevent
	cmd = 'cat '
	threads_list = []
	for p in i['file_list']:
		key = "resource/" + p['url']
		# download(key, 2)
		t = threading.Thread(target=download, args=(key, 2, ))
		threads_list.append(t)
		t.start()
		while threading.activeCount() > 15: time.sleep(.5)
		cmd += '"' + makepath(SAVE_DIR, key) + '" '
	for t in threads_list:
		t.join()
	path = makepath(SAVE_DIR, "resource/" + i['path'])
	os.system(cmd + '> "' + path + '" 2>' + NUL)
	# os.system('cat NUL > ' + SAVE_DIR + "resource/" + i['path'])
	# for p in i['file_list']:
		# os.system('cat ' + SAVE_DIR + "resource/" + p['path'] + ' >> ' + SAVE_DIR + "resource/" + i['path'])
	if md5sum(path) == i['md5']:
		# update("resource/" + i['path'], i['md5'], True)
		dbevent.append(threading.Thread(target=update, args=("resource/" + i['path'], i['md5'], True, )))

def human_int(int):
	cls = ['', 'k', 'M', 'G', 'T', 'P']
	point = 0
	i = 0
	while int > 1024 and i < 5:
		i += 1
		point = int % 1024 // 100
		int = int // 1024
	return str(int) + '.' + str(point) + cls[i]

def read_json(item):
	with open(item, 'r') as f:
		return json.load(f)

def main():
	errorCheck()
	flag = 1
	path = makepath(SAVE_DIR, CONFIG_JSON)
	if os.path.exists(path):
		print('[*] Checking update ...')
		local = read_json(path)
		etag = download(CONFIG_JSON)
		if not ~etag:
			with open(path, 'w') as f:
				json.dump(local, f)
			print("[x] Can't access resources, try a proxy." )
			return -1
		remote = read_json(path)
		if local['version'] == remote['version']:
			print('[*] Asset up to date')
			flag = 0
	else:
		download(CONFIG_JSON)
	if flag:
		threads_list = []
		print('[*] Updating asset lists ...')
		for item in (JSON_LIST + [MOVIE_L_JSON]):
			print('[-] Updating list %s ...' % str(item))
			# download(item)
			t = threading.Thread(target=download, args=(item, ))
			threads_list.append(t)
			t.start()
		for t in threads_list:
			t.join()
	try:
		print('[>] Press Ctrl+C once to break')
		exists = select_all('download_asset')
		d_size = 0
		d_list = []
		# cntp = 0
		for fjson in JSON_LIST:
			print('[*] Loading %s ...' % str(fjson))
			lst = read_json(fjson)
			print('[-] Found %d items' % len(lst))
			for i in lst:
				key = "resource/" + i['path']
				path = makepath(SAVE_DIR, key)
				size = 0
				for p in i['file_list']:
					# cntp += 1
					size += p['size']
				if key not in exists or exists[key] != i['md5'] or not os.path.exists(path) or fsize(path) != size:# or md5sum(path) != i['md5']:
					d_size += size
					d_list.append(i)
		cnti = len(d_list)
		print('[>] Total Download count: ' + str(cnti) + ' size: ' + human_int(d_size) + '. Y/n ')
		readline = input()
		if readline and readline != 'Y' and readline != 'y':
			print('[<] Abort.')
			return
		cnt = 0
		threads_list = []
		for i in d_list:
			cnt += 1
			print('[@] Downloading ' + i['path'] + ', count ' + str(cnt) + '/' + str(cnti) + ', %.')
			if len(i['file_list']) > 1 or i['file_list'][0]['url'] != i['path']:
				# download_p(i)
				t = threading.Thread(target=download_p, args=(i, ))
			else:
				key = "resource/" + i['path']
				# download(key, 1, i['md5'])
				t = threading.Thread(target=download, args=(key, 1, i['md5'], ))
			threads_list.append(t)
			t.start()
			while threading.activeCount() > 15: time.sleep(.5)
		for t in threads_list:
			t.join()
			if len(dbevent):
				dbevent.pop().run()
		while len(dbevent):
			dbevent.pop().run()
	except KeyboardInterrupt:
		pass
	except:
		db.commit()
		db.close()
		raise
	db.commit()
	db.close()
	global FAILLIST
	if len(FAILLIST) > 0:
		with open(makepath(SAVE_DIR, 'fail.log'), 'w') as f:
			f.write("Log time: " + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()) + "\n")
			print("[!] Fail list:")
			for item in FAILLIST:
				print("[x] " + item)
				f.write(item + "\n")

if __name__ == '__main__':
	main()
	exit(0)
