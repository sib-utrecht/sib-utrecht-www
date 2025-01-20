import subprocess
import requests
import os
import re
import argparse
import time
from datetime import datetime, timezone
import pytz
import functools

parser = argparse.ArgumentParser()
parser.add_argument("--verbose", help="Exit on failure", action="store_true")
parser.add_argument("--offline-use", help="Create a static site for offline use instead of serving", action="store_true")
parser.add_argument("--root", help="Starting point", default='/')
args = parser.parse_args()

website = "https://dev2.sib-utrecht.nl"
OUTPUT_DIR_OFFLINE = "cache"
OUTPUT_DIR_HTTP = "static"
OUTPUT_DIR = OUTPUT_DIR_OFFLINE if args.offline_use else OUTPUT_DIR_HTTP

# The site should be open soon so it doesn't matter that the credentials are store in this file for now
auth = ('dev', 'ictcie')
params = {"noauth": "true"}

class Route:
    def __init__(self, path, origpath, linkedfrom, query = ""):
        self.path = path
        self.origpath = origpath
        self.linkedfrom = linkedfrom
        self.query = query
    
    def __str__(self):
        return "'" + self.path + self.query + "'" + " (from '" + self.origpath + "'), linked from '" + self.linkedfrom + "'"

routesTodo = {
    Route(args.root + "404.html", args.root + "404.html", "404"),
    Route(args.root + "symposium", args.root + "symposium", "root point"),
    Route(args.root, args.root, "root point")}
routesDone = set()

USE_FILE_LOCATION = args.offline_use

fileLocation = "file://"
def WriteFile(location, codeBytes):
    os.makedirs(os.path.dirname(location), exist_ok=True)
    file = open(location, 'wb')
    file.write(codeBytes)
    file.close()

def GetFileLocationFromURL(path, use_orig, appendix = "/index.html"):
    out_dir = OUTPUT_DIR_OFFLINE if use_orig else "temp"
    if '.' in path:
        return out_dir + path
    return out_dir + path + appendix

def GetNewUrl(path, for_writing : bool = False, appendix = "/index.html", use_orig : bool = False):
    if USE_FILE_LOCATION:
        rel_path = GetFileLocationFromURL(path, appendix=appendix, use_orig=use_orig)
        if for_writing:
            return rel_path
        return fileLocation + os.path.abspath(rel_path)
    
    if for_writing:
        out_dir = OUTPUT_DIR_HTTP if use_orig else "temp"
        if '.' in path:
            return out_dir + path
        
        assert appendix == "/index.html"
        return out_dir + path + appendix
    
    return path
def RemoveFirstFolder(path):
    (first, second) = os.path.split(path)
    if second == "":
        ""
    if first == "":
        return second
    return os.path.join(RemoveFirstFolder(first), second)
def GetUrlFromFileLocation(filepath):
    if not args.offline_use:
        return filepath
    filepath = os.path.relpath(filepath)
    if filepath.endswith('/index.html'):
        filepath = filepath[:-len('/index.html')]
    filepath = RemoveFirstFolder(filepath)
    return filepath
        
def GetLocationOfTimestampFromURL(path, use_orig):
    return f"{GetNewUrl(path, for_writing=True, use_orig=use_orig)}.time"

def Download(path):
    r = requests.get(website + path, auth = auth, params=params)
    if r.status_code == 404 and path == "/404.html":
        return r.content

    # Also fails on 404
    r.raise_for_status()
    return r.content

def ShouldRedownload(route, time):
    if route.path == "/404.html":
        return False
    if route.path.startswith("/restricted"):
        return False
    if route.path.endswith(".woff2"):
        return False
    # Todo: should check that the version queried (route.query) is the same as the only previously downloaded
    if route.path.endswith(".js") or route.path.endswith(".css"):
        return False
    path = route.path
    try:
        if time >= MODIFICATION_TIMES[path]:
            return False
    except:
        print(f"WARNING: File didn't exist in the database of modified times {route.path}")
    return True


# Return (content, wasDownloaded)
def Get(route):
    if (os.path.exists(GetNewUrl(route.path, for_writing=True, use_orig=True))):
        with open(GetLocationOfTimestampFromURL(route.path, use_orig=True)) as f:
            time = datetime.fromisoformat(f.read()).replace(tzinfo=timezone.utc)
        if (not ShouldRedownload(route, time)):
            with open(GetNewUrl(route.path, for_writing=True, use_orig=True), "rb") as f:
                print(f"Moving file {route.path} from previous download...", end="")
                return (f.read(), False)
        else:
            print(f"File {route.path} is invalidated and will be redownloaded...", end="")
    else:
        print(f"File {route.path} did not exist in previous download: downloading...", end="")
    return (Download(route.path), True)

def ParseLink(link, wasDownloaded = True):
    changed = False
    query = ""

    if link.startswith(website):
        changed = True
        link = link[len(website):]
    loc = link.find('#')
    if loc != -1:
        changed = True
        query = link[loc:] + query
        link = link[:loc]
        

    loc = link.find('?') # for now we remove these because it doesn't play nice with with file naming
    if loc != -1:
        changed = True
        query = link[loc:] + query
        link = link[:loc]

    # links to homepage can become empty after removing the website, but already empty links should be ignored
    if link == '' and changed:
        link = '/'
    # maybe should remove xmlrpc (https://www.hostinger.com/tutorials/xmlrpc-wordpress)
    # the wp-json is temporary
    if link.startswith('http') or 'xmlrpc' in link or 'mailto' in link or ':' in link or 'wp-json' in link or "/feed" in link: # the : appears in svg urls
        return None, None
    if wasDownloaded:
        return link, query
    else:
        return GetUrlFromFileLocation(link), query

def AddRoute(route):
    if route.path.endswith('/') and len(route.path) > 1:
        route.path = route.path[:-1]

    if route.path not in routesDone:
        routesTodo.add(route)

headRemoveReferences = re.compile("<link [^>]+//dev2.sib-utrecht.nl[^>]+>")
linkRegex = re.compile("(href|src)(\\s*)(\\^)?=(\\s*)(\"|')(.*?)(\"|')")
urlRegex = re.compile("url\\((\"|'|\\&\\#039\\;)?(.*?)(\"|'|\\&\\#039\\;)?\\)")
srcsetRegex = re.compile("srcset(\\s*)=(\\s*)(\"|')(.*?)(\"|')")
stringRegex = re.compile("\"https:\\\\?/\\\\?/dev2.sib-utrecht.nl(\\\\?/[^\"]*)\"")

def FindNewRoutes(code, currentPath, wasDownloaded):
    res = linkRegex.finditer(code)
    for found in res:
        path = found.group(6)
        if path == "//cdn.jsdelivr.net":
            continue
        origpath = path
        path, query = ParseLink(path, wasDownloaded)
        if path != None:
            AddRoute(Route(path, origpath, currentPath, query))

    res = urlRegex.finditer(code)
    for found in res:
        path = found.group(2)
        origpath = path
        path, query = ParseLink(path, wasDownloaded)
        if path != None:
            AddRoute(Route(path, origpath, currentPath, query))

    res = srcsetRegex.finditer(code)
    for found in res:
        srcs = found.group(4).split(',')
        for link in srcs:
            path = link.split()[0] # Important: same as below
        path, query = ParseLink(path, wasDownloaded)
        if path != None:
            AddRoute(Route(path, origpath, currentPath, query))

    res = stringRegex.finditer(code)
    for found in res:
        path = found.group(1).replace('\\/', '/')
        if path == '/wp-admin/admin-ajax.php':
            continue

        origpath = path
        path, query = ParseLink(path,wasDownloaded)
        if path != None:
            AddRoute(Route(path, origpath, currentPath, query))

def SubsituteRoutes(code, currentPath):
    def subNormalLink(match):
        path, query = ParseLink(match.group(6))

        if path == None:
            return match.group()
        if match.group(3) == None:
            appendix = "/index.html"
            caret = ""
        else:
            appendix = ""
            caret = "^"
        return match.group(1) + match.group(2) + caret + "=" + match.group(4) + match.group(5) + GetNewUrl(path, appendix=appendix, use_orig=True) + query + match.group(7)
    def subUrlLink(match):
        path, query = ParseLink(match.group(2))
        if path == None:
            return match.group()
        closingDelimeter = match.group(1)
        if closingDelimeter == None:
            closingDelimeter = ''
        return "url(" + closingDelimeter + GetNewUrl(path, use_orig=True) + query + closingDelimeter + ')'

    def subSrcset(match):
        output = []
        srcs = match.group(4).split(',')
        for src in srcs:
            split = src.split() # Important: don't give parameters to split in order to split on multiple consecutive whitespaces
            if len(split) == 1:
                # This can apparently happen in a carousel as a srcset without the second part for some reason
                split += " "
            path, query = ParseLink(split[0])
            if path == None:
                output.append(src + ' ' + split[1])
                continue
            output.append(GetNewUrl(path, use_orig=True) + query + ' ' + split[1])
        return "srcset=" + match.group(3) + ','.join(output) + match.group(5)
    
    def subString(match):
        path, query = ParseLink(match.group(1))
        if path == None:
            return match.group()
        return "\"" + GetNewUrl(path, use_orig=True) + query + "\""

    code = linkRegex.sub(subNormalLink, code)
    code = urlRegex.sub(subUrlLink, code)
    code = srcsetRegex.sub(subSrcset, code)
    code = stringRegex.sub(subString, code)
    code = headRemoveReferences.sub("", code)
    return code

def CheckCodeForLinks(code, currentPath):
    FindNewRoutes(code, currentPath)
    return SubsituteRoutes(code, currentPath)

TIME_FORMAT = "%Y-%m-%dT%H:%M:%S"

def HandleSingleFile(nextRoute):
    if nextRoute.path == "/restricted/documents" or nextRoute.path == "/restricted" or nextRoute.path == "/restricted/":
        # For now just ignore this, because these paths are relative
        return
    try:
        (fileBytes, wasDownloaded) = Get(nextRoute)
        routesDone.add(nextRoute.path)
        try:
            if ('.js' not in nextRoute.path):
                # we just assume all pages are utf-8 encoded
                decoded = fileBytes.decode('utf-8')
                FindNewRoutes(decoded, nextRoute.path, wasDownloaded)
                if wasDownloaded:
                    fileBytes = SubsituteRoutes(decoded, nextRoute.path).encode('utf-8')
        except UnicodeError as e:
            pass
        if wasDownloaded:
            WriteFile(GetNewUrl(nextRoute.path, for_writing=True), fileBytes)
        else:
            dest = GetNewUrl(nextRoute.path, for_writing=True)
            subprocess.run(["mkdir", "-p", os.path.split(dest)[0]])
            subprocess.run(["mv", GetNewUrl(nextRoute.path, for_writing=True, use_orig=True), GetNewUrl(nextRoute.path, for_writing=True)])
        with open(GetLocationOfTimestampFromURL(nextRoute.path, False), "w") as f:
            f.write(time_now)
        print("Done.")
    except Exception as e:
        if args.verbose:
            print("Something went wrong while working on path ", nextRoute)
            print(e)
            exit(-1)
        else:
            print("\nWARNING: something went wrong while working on path ", nextRoute)
            print(e)

time_now = datetime.now(timezone.utc).strftime(TIME_FORMAT)
def DownloadEverything():
    while len(routesTodo) != 0:
        nextRoute = routesTodo.pop()
        if nextRoute.path not in routesDone:
            HandleSingleFile(nextRoute)

MODIFICATION_TIMES = {}

def GetModificationDates(path):
    global MODIFICATION_TIMES
    page_num = 1
    while True:
        r = requests.get(f"{website}{path}?page={page_num}&per_page=100", auth=auth, params=params) # The limit for per_page is 100
        if (r.status_code == 400):
            # We reached the end
            break

        json = r.json()
        for page in json:
            modified_time = datetime.strptime(page['modified'], TIME_FORMAT).replace(tzinfo=timezone.utc) # The site's time is in utc
            try:
                links = [page['source_url']]
                for size in page['media_details']['sizes']:
                    links.append(page['media_details']['sizes'][size]['source_url'])
            except:
                links = [page['link']]
            for link in links:
                if not link.startswith(website):
                    if args.verbose:
                        raise Exception("Error: linked page '" + link + "' is not a SIB-page!")
                    else:
                        print(f"WARNING: linked page '{link}' is not a SIB page")
                        continue
                currentpath = link[len(website):]
                if currentpath.endswith('/') and len(currentpath)> 1:
                    currentpath = currentpath[:-1]
                MODIFICATION_TIMES[currentpath] = modified_time
        
        page_num += 1


def GetModificationDatesForEvents():
    global MODIFICATION_TIMES
    r = requests.get(f"https://api.sib-utrecht.nl/v2/events")

    json = r.json()
    for page in json['data']['events']:
        modified_time = datetime.fromisoformat(page['$.modified'])
        link = f"/activities/{page['id']}"
        MODIFICATION_TIMES[link] = modified_time


def SetupUpdate():
    subprocess.run(["mkdir", "temp"])
    GetModificationDates("/wp-json/wp/v2/pages")
    GetModificationDates("/wp-json/wp/v2/media")
    GetModificationDatesForEvents()
    
def CleanupUpdate():
    if USE_FILE_LOCATION:
        output_dir = OUTPUT_DIR_OFFLINE
    else:
        output_dir = OUTPUT_DIR_HTTP
    subprocess.run(["rm", "-r", output_dir])
    subprocess.run(["mv", "temp", output_dir])

print("Starting the scraping")
SetupUpdate()
print("Downloaded all modification dates. Now downloading the pages.")
DownloadEverything()
print("Finished downloading all pages. Now cleaning up")
CleanupUpdate()
print("Finished downloading!")
