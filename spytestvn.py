from urllib.parse import urlparse, urljoin
from colorama import init, Fore
from tqdm import tqdm
import questionary, subprocess, requests, socket, time, sys, re, io


init(autoreset=True)
ping_count = 2
download_size = 50 #MB
upload_size = 50 #MB
unit_divisor = 1024
unit = 'B'
bar_format = '{desc} {rate_fmt} {bar:80}'

def get_servers():
  try:
    r = requests.get('https://speedtest.vn/get-servers', allow_redirects=False)
    if r.status_code != 200:
      sys.exit(Fore.YELLOW + 'HTTP status code=' + f'{r.status_code}')
    return r.json()
  except requests.exceptions.RequestException as err:
    print(Fore.RED + f'{err}')
    sys.exit(Fore.YELLOW + 'Get servers configuration failed')

def ask_for_server(servers):
  return questionary.select(
    'Select a server to test:',
    choices=list(map(
      lambda sv: questionary.Choice(f"{sv['name']} - {sv['city']}", sv),
      servers))
  ).ask()

def myip_info():
  try:
    return requests.get('https://speedtest.vn/get-ip-info?isp=true').json()
  except requests.exceptions.RequestException:
    return {'ip': 'unknown', 'isp': 'unknown'}

def ping (hostname):
  ping_option = f"-i 0.2 -4 {'-n' if sys.platform.lower() == 'windows' else '-c'} {ping_count}"
  ping_command = f'ping {ping_option} {hostname}'
  process = subprocess.Popen(ping_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  out, err = process.communicate()
  if len(err) > 0:
    return {'latency': '-1', 'jitter': '0'}
  # im not sure if mdev is jitter or not lmao
  m = re.search('rtt min/avg/max/mdev = (\d+.\d+)/(\d+.\d+)/(\d+.\d+)/(\d+.\d+)', str(out))
  return {'latency': m.group(2), 'jitter': m.group(4)}

def url_sep(url):
  return '&' if re.match('\?', url) else '?'

def download_test(url):
  bar = create_bar(download_size * 1<<20, desc='Download speed:')
  r = requests.get(url, stream=True)
  for chunk in r.iter_content(chunk_size=8192):
    bar_update(bar, len(chunk))

def create_bar(total, desc=None):
  return tqdm(desc=desc, total=total, unit_scale=True, unit_divisor=unit_divisor, unit=unit, bar_format=bar_format)

def bar_update(bar, n):
  bar.update(n)

def upload_test(url):
  file = create_file_to_upload()
  bar = create_bar(upload_size * 1<<20, desc='Upload speed:')
  body = FileIOCB(file, bar_update, [bar])
  r = requests.post(url, data=body)

def create_file_to_upload():
  filename = 'you_can_delete_this'
  f = open(filename,'wb')
  f.seek((upload_size * 1<<20) - 1)
  f.write(b"\0")
  f.close()
  return filename

class FileIOCB(io.BytesIO):
  def __init__(self, file, callback=None, cb_args=()):
    buf = open(file, 'rb').read()
    self._len = len(buf)
    self._callback = callback
    self._cb_args = cb_args
    io.BytesIO.__init__(self, buf)

  def __len__(self):
    return self._len

  def read(self, n=-1):
    chunk = io.BytesIO.read(self, n)
    if self._callback:
      try:
        self._callback(*self._cb_args, len(chunk))
      except:
        pass
    return chunk


def main(argv):
  print('Getting servers configuration...')
  servers = get_servers()
  server = ask_for_server(servers)
  u = urlparse(server['baseUrl'])
  print('Server IP:', socket.gethostbyname(u.hostname))
  ip_info = myip_info()
  print('Your IP:', ip_info['ip'])
  print('Your ISP:', ip_info['isp'])
  ping_result = ping(u.hostname)
  print('Ping:', ping_result['latency'], 'ms')
  print('Jitter:', ping_result['jitter'], 'ms')
  download_test(urljoin(server['baseUrl'], f"{server['downloadUrl']}{url_sep(server['downloadUrl'])}ckSize={download_size}"))
  upload_test(urljoin(server['baseUrl'], server['uploadUrl']))
  

if __name__ == '__main__':
  main(sys.argv[1:])