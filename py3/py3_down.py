#!/usr/bin/python3
# coding=utf-8
import os
import re
import sys
import json
import time
import sqlite3
# import urllib.request as request
import threading

if os.name == 'nt':
	NUL = "NUL"
	cat = "type "
	rm = "del /Q "
else:
	NUL = "/dev/null"
	cat = "cat "
	rm = "rm -f "

def makepath(p1, p2):
	for i in p2.split('/'):
		p1 = os.path.join(p1, i)
	return p1

quite = False
verbose = False
clean = False
ttime = False
log = True

UA = "Mozilla/5.0 (Linux; Android 7.1.2; PIXEL 2 XL Build/NOF26V; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/72.0.3626.121 Mobile Safari/537.36"
CURL_CONFIG = ""
HTTPS = "https://"
GAME_HOST = "android.magi-reco.com"
# RESOLVE = "2600:9000:2012:7200:19:70ed:2780:93a1"
# MASTER_PATH = ""
# ERROR403 = ""
ERRORLEN = 6351
ERRORTAG = '"d35a7bb0529c5095e8da9113c4ca5578"'

CONFIG_JSON    = "asset_config.json"
MAIN_JSON      = "asset_main.json"
MOVIE_H_JSON   = "asset_movie_high.json"
MOVIE_L_JSON   = "asset_movie_low.json"
VOICE_JSON     = "asset_voice.json"
CHAR_LIST_JSON = "asset_char_list.json"
FULLVOICE_JSON = "asset_fullvoice.json"
PROLOGUE_VOICE = "asset_prologue_voice.json"
PROLOGUE_MAIM  = "asset_prologue_main.json"


SAVE_DIR = os.path.dirname(os.path.realpath(__file__))
# RESOURCE_DIR = ""
JSON_LIST = [MAIN_JSON, VOICE_JSON, MOVIE_H_JSON, CHAR_LIST_JSON, FULLVOICE_JSON, PROLOGUE_VOICE, PROLOGUE_MAIM]
MAXTHREAD = 7
d_piece = 0
d_size = 0
d_recv = 0
d_count = 0
lock = threading.Lock()
FAILLIST = []
# db = ""
# cursor = ""

dbevent = []

def select_all(table):
	cursor = db.execute("SELECT * FROM " + table)
	res = {}
	for row in cursor:
		res[row[0]] = row[1]
	cursor.close()
	return res

def update(file, md5, type):
	global d_piece, d_recv, d_count, d_size
	if type:
		table = 'download_asset'
		key = 'path'
		value = 'md5'
		if not quite: print('\r[@] %6.2f%% - %d/%d #//--' % (d_recv / d_size * 100, d_count, d_piece), file=sys.stderr, end='\r')
	else:
		table = 'asset_json'
		key = 'file'
		value = 'etag'
	res = db.execute("SELECT * FROM {} WHERE {} = '{}'".format(table, key, file))
	if len(res.fetchall()):
		cursor = db.execute("UPDATE {} SET {} = '{}' WHERE {} = '{}'".format(table, value, md5, key, file))
	else:
		cursor = db.execute("INSERT INTO {} ({}, {}) VALUES ('{}', '{}')".format(table, key, value, file, md5))
	res.close()
	cursor.close()
	db.commit()

def md5sum(path):
	with os.popen('md5sum "' + path + '" | cut -d " " -f 1') as f:
		return f.read().strip()

def fsize(path):
	return os.stat(path).st_size

def errorCheck():
	global ERRORTAG, ERRORLEN
	with os.popen('curl -I ' + ERROR403 + CURL_CONFIG + ' 2>' + NUL) as f:
		head = f.read()
	e = re.search(r'ETag: (.*)\n', head, re.I)
	if not e:
		print("[x] Network ERROR, check config.")
		exit(-1)
	etag = e[1]
	cl = re.search(r'Content-Length: (.*)\n', head, re.I)[1]
	ERRORTAG = etag
	ERRORLEN = int(cl)

# type 0: json; 1: item; 2: part;
def download(item, type = 0, md5 = ""):
	global d_recv, d_count, FAILLIST, dbevent
	try:
		path = os.path.dirname(makepath(SAVE_DIR, item))
		if not os.access(path, os.F_OK):
			os.makedirs(path)
	except FileExistsError:
		pass
	except:
		raise
	path = makepath(SAVE_DIR, item)
	islock = False
	try:
		with os.popen('curl -v -o "' + path + '" "' + MASTER_PATH + item + '"' + CURL_CONFIG + ' 2>&1') as f:
			head = f.read()
		lm = re.search(r'Last-Modified: (.*)\n', head, re.I)[1]
		etag = re.search(r'ETag: (.*)\n', head, re.I)[1]
		cl = int(re.search(r'Content-Length: (.*)\n', head, re.I)[1])
		islock = lock.acquire()
		d_recv += cl
		d_count += 1
		islock = lock.release()
		if etag == ERRORTAG or cl == ERRORLEN:
			FAILLIST.append(item)
			return 403
		if type == 0:
			if MAXTHREAD > 1:
				dbevent.append(threading.Thread(target=update, args=(item, etag, False, )))
			else:
				update(item, etag, False)
		elif type == 1:
			if MAXTHREAD > 1:
				dbevent.append(threading.Thread(target=update, args=(item, md5, True, )))
			else:
				update(item, md5, True)
		if ttime: os.system('touch "' + path + '" -d "' + lm + '"')
		return 0
	except KeyboardInterrupt:
		if islock: lock.release()
		raise
	except:
		if islock: lock.release()
		FAILLIST.append(item)
	return -1

def download_p(i):
	global dbevent
	l = ""
	threads_list = []
	for p in i['file_list']:
		key = "resource/" + p['url']
		if MAXTHREAD > 1:
			t = threading.Thread(target=download, args=(key, 2, ))
			threads_list.append(t)
			t.start()
			while threading.activeCount() > MAXTHREAD: time.sleep(.5)
		else:
			download(key, 2)
		l += '"' + makepath(SAVE_DIR, key) + '" '
	for t in threads_list:
		t.join()
	path = makepath(SAVE_DIR, "resource/" + i['path'])
	os.system(cat + l + '> "' + path + '" 2>' + NUL)
	if ttime: os.system('touch -c "' + path + '" -r "' + makepath(RESOURCE_DIR, i['file_list'][0]['url']) + '"')
	if clean: os.system(rm + l + '> ' + NUL + ' 2>' + NUL)
	# os.system('cat NUL > ' + SAVE_DIR + "resource/" + i['path'])
	# for p in i['file_list']:
		# os.system('cat ' + SAVE_DIR + "resource/" + p['path'] + ' >> ' + SAVE_DIR + "resource/" + i['path'])
	if md5sum(path) == i['md5']:
		if MAXTHREAD > 1:
			dbevent.append(threading.Thread(target=update, args=("resource/" + i['path'], i['md5'], True, )))
		else:
			update("resource/" + i['path'], i['md5'], True)

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
	global d_count, d_recv, d_piece, d_size
	errorCheck()
	flag = 1
	path = makepath(SAVE_DIR, CONFIG_JSON)
	if os.path.exists(path):
		if not quite: print('[*] Checking update ...')
		local = read_json(path)
		if download(CONFIG_JSON):
			with open(path, 'w') as f:
				json.dump(local, f)
			print("[x] Can't access resources, try a proxy." )
			return -2
		remote = read_json(path)
		if local['version'] == remote['version']:
			print('[*] Asset up to date')
			flag = 0
	else:
		download(CONFIG_JSON)
	if flag:
		threads_list = []
		if not quite: print('[*] Updating asset lists ...')
		for item in (JSON_LIST + [MOVIE_L_JSON]):
			if not quite: print('[-] Updating list %s ...' % str(item))
			if MAXTHREAD > 1:
				t = threading.Thread(target=download, args=(item, ))
				threads_list.append(t)
				t.start()
			else:
				download(item)
		for t in threads_list:
			t.join()
	try:
		exists = select_all('download_asset')
		d_list = []
		d_recv = 0
		d_count = 0
		for fjson in JSON_LIST:
			if not quite: print('[*] Loading %s ...' % str(fjson))
			lst = read_json(makepath(SAVE_DIR, fjson))
			if not quite: print('[-] Found %d items' % len(lst))
			for i in lst:
				key = "resource/" + i['path']
				path = makepath(SAVE_DIR, key)
				size = 0
				cntp = 0
				for p in i['file_list']:
					cntp += 1
					size += p['size']
				if not os.path.exists(path) or fsize(path) != size or key not in exists or exists[key] != i['md5']:# or md5sum(path) != i['md5']:
					d_piece += cntp
					d_size += size
					d_list.append(i)
					if verbose: print('[ ] ' + i['path'])
		if not len(d_list): return 0
		if log:
			hdir = makepath(SAVE_DIR, "history")
			if not os.access(hdir, os.F_OK):
				os.makedirs(hdir)
			with open(makepath(hdir, time.strftime("%Y%m%d_%H%M", time.localtime()) + '.html'), 'w') as f:
				#with open(makepath(SAVE_DIR, 'history/head.html'), 'w') as h: f.write(h.read())
				for i in d_list: f.write('<li><a href="/magica/resource/' + i['path'] + '">' + i['path'] + "</a>&emsp;(" + i['md5'] + ")" + "</li>\n")
				#with open(makepath(SAVE_DIR, 'history/foot.html'), 'w') as h: f.write(h.read())
		print('[>] Summary: ' + str(len(d_list)) + ' files, with ' + str(d_piece) + ' pieces, size: ' + human_int(d_size) + '. ', end='')
		if quite:
			print()
		else:
			print('Y/n? ', end='')
			k = input()
			if k and k != 'Y' and k != 'y':
				print('[<] Abort.')
				return -1
			print('[>] Press Ctrl+C ONCE to break')
		if not quite: print('[*] Start download ...')
		cnt = 0
		threads_list = []
		for i in d_list:
			cnt += 1
			if len(i['file_list']) > 1 or i['file_list'][0]['url'] != i['path']:
				if MAXTHREAD > 1: t = threading.Thread(target=download_p, args=(i, ))
				else: download_p(i)
			else:
				key = "resource/" + i['path']
				if MAXTHREAD > 1: t = threading.Thread(target=download, args=(key, 1, i['md5'], ))
				else: download(key, 1, i['md5'])
			if MAXTHREAD > 1: threads_list.append(t)
		for t in threads_list:
			while threading.activeCount() > MAXTHREAD: time.sleep(.5)
			t.start()
			if len(dbevent): dbevent.pop().run()
		for t in threads_list:
			t.join()
			if len(dbevent): dbevent.pop().run()
		while len(dbevent): dbevent.pop().run()
		print()
		print('[.] Finished.')
	except KeyboardInterrupt:
		print()
		print('[<] Abort by user.')
		return -1
	except:
		print('[x] Runtime Error')
		raise
	global FAILLIST
	if len(FAILLIST) > 0:
		with open(makepath(SAVE_DIR, 'fail.log'), 'w') as f:
			f.write("Log time: " + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()) + "\n")
			print("[!] Fail list:")
			for item in FAILLIST:
				print("[x] " + item)
				f.write(item + "\n")
	return 0;

def de(t):
	t = t.lower()
	if t == 'a' or t == 'all':
		return [MAIN_JSON, VOICE_JSON, MOVIE_L_JSON, MOVIE_H_JSON, CHAR_LIST_JSON, FULLVOICE_JSON, PROLOGUE_VOICE, PROLOGUE_MAIM]
	if t == 'm' or t == 'ma' or t == 'main':
		return [MAIN_JSON]
	if t == 'v' or t == 'vo' or t == 'voice':
		return [VOICE_JSON]
	if t == 'f' or t == 'fv' or t == 'fullvoice':
		return [FULLVOICE_JSON]
	if t == 'mh' or t == 'h' or t == 'movie_h' or t == 'high' or t == 'movie_high':
		return [MOVIE_H_JSON]
	if t == 'ml' or t == 'l' or t == 'movie_l' or t == 'low' or t == 'movie_low':
		return [MOVIE_L_JSON]
	if t == 'mov' or t == 'movie':
		return [MOVIE_H_JSON, MOVIE_L_JSON]
	if t == 'c' or t == 'char' or t == 'char_list':
		return [CHAR_LIST_JSON]
	if t == 'pv' or t == 'prologue_voice':
		return [PROLOGUE_VOICE]
	if t == 'pm' or t == 'prologue_main':
		return [PROLOGUE_MAIM]
	if t == 'p' or t == 'prologue':
		return [PROLOGUE_MAIM, PROLOGUE_VOICE]
	raise Exception("Unknow Asset")

pram = ""
if __name__ == '__main__':
	for i in sys.argv:
		if pram:
			if pram == 'E':
				JSON_LIST += de(i)
			elif pram == 'D':
				for j in de(i):
					if j in JSON_LIST: JSON_LIST.remove(j)
			elif pram == 'U':
				UA = i
			elif pram == 'H':
				t = re.match(r'^http(s)?://(.*)', i)
				if t:
					GAME_HOST = t.group(2)
					HTTPS = "https://" if t.group(1) else "http://"
				else: GAME_HOST = t.group(1)
			elif pram == 'r':
				if HTTPS == "http://": CURL_CONFIG += ' --resolve ' + GAME_HOST + ':80:' + i
				else:                  CURL_CONFIG += ' --resolve ' + GAME_HOST + ':443:' + i
			elif pram == 'P':
				CURL_CONFIG += ' -x ' + i
			elif pram == 's':
				SAVE_DIR = i
			pram = ""
			continue
		if i[0] == '-':
			if i == '-h' or i == '--help':
				print('Usage: python3 py3_down.py [option] [MAXTHREAD = 7]')
				print('Magia Record mulit-thread data downloader, base on cURL.')
				print('    -h, --help   Show this help.')
				print('    -q, -y       Quite mode, download without ask.')
				print('    -n           Do not write html history.')
				print('    -c           remove split pieces (*.a??).')
				print('    -t           Touch file with server time.')
				print('    -v           Show download list.')
				print('    -U UserAgent Set custom UA.')
				print('    -H Host      Set Magireco domain. Must before -r.')
				print('    -r ip        Set ip for Magireco domain.')
				print('    -P proxy     Set proxy for cURL.')
				print('    -s dir       Set Save dir.')
				print('    -E[asset]    Enable a asset.')
				print('    -D[asset]    Disable a asset.')
				print()
				print('        Avaliable assets:')
				print('                 asset_main.json           : m, ma, main')
				print('                 asset_voice.json          : v, vo, voice')
				print('                 asset_fullvoice.json      : f, fv, fullvoice')
				print('                 asset_movie_high.json     : h, mh, high, movie_h, movie_high')
				print('                 asset_movie_low.json      : l, ml, low, movie_l, movie_low ')
				print('                 BOTH TWO ABOVE            : mov, movie')
				print('                 asset_char_list.json      : c, char, char_list')
				print('                 asset_prologue_main.json  : pv, prologue_voice')
				print('                 asset_prologue_voice.json : pm, prologue_main')
				print('                 BOTH TWO ABOVE            : p, prologue')
				print('                 ALL ABOVE                 : a, all')
				print('        Default with -E all -D low')
				print('    MAXTHREAD    Maximum thread number. When 1 set to single thread mode.')
				exit(0)
			if i in ['-E', '-D', '-U', '-H', '-r', '-P', '-s']:
				pram = i[1:]
				continue
			if i[1] == 'q' or i[1] == 'y':
				quite = True
				continue
			if i[1] == 'n':
				log = False
				continue
			if i[1] == 'c':
				clean = True
				continue
			if i[1] == 't':
				ttime = True
				continue
			if i[1] == 'v':
				verbose = True
				continue
			if i[1] == 'E':
				JSON_LIST += de(i[2:])
				continue
			if i[1] == 'D':
				for j in de(i[2:]):
					if j in JSON_LIST: JSON_LIST.remove(j)
				continue
		else: 
			if i.isdigit():
				MAXTHREAD = int(i)
	# Config
	CURL_CONFIG += ' -H "User-Agent: ' + UA + '"'
	MASTER_PATH = HTTPS + GAME_HOST + "/magica/resource/download/asset/master/"
	ERROR403 = HTTPS + GAME_HOST
	RESOURCE_DIR = makepath(SAVE_DIR, "resource")
	db = sqlite3.connect(makepath(SAVE_DIR, 'madomagi.db'))
	cursor = db.execute("SELECT COUNT(*) FROM sqlite_master where type='table' and name='download_asset'")
	if not cursor.fetchone()[0]:
		db.execute("CREATE TABLE download_asset(path char(128) primary key,md5 char(128))")
	cursor.close()
	cursor = db.execute("SELECT COUNT(*) FROM sqlite_master where type='table' and name='asset_json'")
	if not cursor.fetchone()[0]:
		db.execute("CREATE TABLE asset_json(file char(128) primary key,etag char(128))")
	cursor.close()

	# Strat
	print('[' + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()) + ']')
	r = main()
	print('[' + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()) + ']')
	exit(r)
