import requests
import os
import re
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--verbose", help="Print every downloaded files and exit on failure", action="store_true")
parser.add_argument("--offline-use", help="Create a static site for offline use instead of serving", action="store_true")
parser.add_argument("--root", help="Starting point", default='/')
args = parser.parse_args()

website = "https://dev2.sib-utrecht.nl"
OUTPUT_DIR_OFFLINE = "cache"
OUTPUT_DIR_HTTP = "static"
# folder = 

# The site should be open soon so it doesn't matter that the credentials are store in this file for now
auth = ('dev', 'ictcie')

class Route:
    def __init__(self, path, origpath, linkedfrom):
        self.path = path
        self.origpath = origpath
        self.linkedfrom = linkedfrom
    
    def __str__(self):
        return "'" + self.path + "'" + " (from '" + self.origpath + "'), linked from '" + self.linkedfrom + "'"

routesTodo = {
    Route(args.root + "404.html", args.root + "404.html", "404"),
    Route(args.root, args.root, "root point")}
routesDone = set()

USE_FILE_LOCATION = args.offline_use

fileLocation = "file://"
def WriteFile(location, codeBytes):
    os.makedirs(os.path.dirname(location), exist_ok=True)
    file = open(location, 'wb')
    file.write(codeBytes)
    file.close()

def GetFileLocationFromURL(path, appendix = "/index.html"):
    if '.' in path:
        return OUTPUT_DIR_OFFLINE + path
    return OUTPUT_DIR_OFFLINE + path + appendix

def GetNewUrl(path, for_writing : bool = False, appendix = "/index.html"):
    if USE_FILE_LOCATION:
        rel_path = GetFileLocationFromURL(path, appendix=appendix)
        if for_writing:
            return rel_path
        return fileLocation + os.path.abspath(rel_path)
    
    if for_writing:
        if '.' in path:
            return OUTPUT_DIR_HTTP + path
        
        assert appendix == "/index.html"
        return OUTPUT_DIR_HTTP + path + appendix
    
    return path
        

def Download(path):
    r = requests.get(website + path, auth = auth)
    if r.status_code == 404 and path == "/404.html":
        return r.content

    # Also fails on 404
    r.raise_for_status()
    return r.content

def ParseLink(link):
    changed = False
    query = ""

    if link.startswith(website):
        changed = True
        link = link[len(website):]
    loc = link.find('#')
    if loc != -1:
        # print(f"Found # at position {loc} in {link}")
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
    if link.startswith('http') or 'xmlrpc' in link or 'mailto' in link or ':' in link or 'wp-json' in link: # the : appears in svg urls
        return None, None
    return link, query

def AddRoute(route):
    if route.path not in routesDone:
        routesTodo.add(route)

headRemoveReferences = re.compile("<link [^>]+//dev2.sib-utrecht.nl[^>]+>")
linkRegex = re.compile("(href|src)(\\s*)(\\^)?=(\\s*)(\"|')(.*?)(\"|')")
urlRegex = re.compile("url\\((\"|'|\\&\\#039\\;)?(.*?)(\"|'|\\&\\#039\\;)?\\)")
srcsetRegex = re.compile("srcset(\\s*)=(\\s*)(\"|')(.*?)(\"|')")
stringRegex = re.compile("\"https:\\\\?/\\\\?/dev2.sib-utrecht.nl(\\\\?/[^\"]*)\"")

def FindNewRoutes(code, currentPath):
    res = linkRegex.finditer(code)
    for found in res:
        path = found.group(6)
        origpath = path
        path, _ = ParseLink(path)
        if path != None:
            AddRoute(Route(path, origpath, currentPath))

    res = urlRegex.finditer(code)
    for found in res:
        path = found.group(2)
        origpath = path
        path, _ = ParseLink(path)
        if path != None:
            AddRoute(Route(path, origpath, currentPath))

    res = srcsetRegex.finditer(code)
    for found in res:
        srcs = found.group(4).split(',')
        for link in srcs:
            path = link.split()[0] # Important: same as below
            origpath = path
            path, _ = ParseLink(path)
            if path != None:
                routesTodo.add(Route(path, origpath, currentPath))

    res = stringRegex.finditer(code)
    for found in res:
        path = found.group(1).replace('\\/', '/')
        if path == '/wp-admin/admin-ajax.php':
            continue

        origpath = path
        path, _ = ParseLink(path)
        if path != None:
            AddRoute(Route(path, origpath, currentPath))



def SubsituteRoutes(code, currentPath):
    def subNormalLink(match):
        path, query = ParseLink(match.group(6))
        # print(f"SubNormalLink, full={match.group(6)}, path={path}, query={query}")

        if path == None:
            return match.group()
        if match.group(3) == None:
            appendix = "/index.html"
            caret = ""
        else:
            appendix = ""
            caret = "^"
        return match.group(1) + match.group(2) + caret + "=" + match.group(4) + match.group(5) + GetNewUrl(path, appendix=appendix) + query + match.group(7)
    def subUrlLink(match):
        path, query = ParseLink(match.group(2))
        if path == None:
            return match.group()
        closingDelimeter = match.group(1)
        if closingDelimeter == None:
            closingDelimeter = ''
        return "url(" + closingDelimeter + GetNewUrl(path) + query + closingDelimeter + ')'

    def subSrcset(match):
        output = []
        srcs = match.group(4).split(',')
        for src in srcs:
            split = src.split() # Important: don't give parameters to split in order to split on multiple consecutive whitespaces
            path, query = ParseLink(split[0])
            if path == None:
                output.append(src + ' ' + split[1])
                continue
            output.append(GetNewUrl(path) + query + ' ' + split[1])
        return "srcset=" + match.group(3) + ','.join(output) + match.group(5)
    
    def subString(match):
        path, query = ParseLink(match.group(1))
        if path == None:
            return match.group()
        return "\"" + GetNewUrl(path) + query + "\""
    
    code = headRemoveReferences.sub("", code)
    code = linkRegex.sub(subNormalLink, code)
    code = urlRegex.sub(subUrlLink, code)
    code = srcsetRegex.sub(subSrcset, code)
    code = stringRegex.sub(subString, code)
    return code

def CheckCodeForLinks(code, currentPath):
    FindNewRoutes(code, currentPath)
    return SubsituteRoutes(code, currentPath)

print("Starting the download")
while len(routesTodo) != 0:
    nextRoute = routesTodo.pop()
    if nextRoute.path not in routesDone:
        try:
            fileBytes = Download(nextRoute.path)
            routesDone.add(nextRoute.path)
            try:
                if ('.js' not in nextRoute.path):
                    # we just assume all pages are utf-8 encoded
                    decoded = fileBytes.decode('utf-8')
                    fileBytes = CheckCodeForLinks(decoded, nextRoute.path).encode('utf-8')
            except UnicodeError as e:
                pass
            WriteFile(GetNewUrl(nextRoute.path, for_writing=True), fileBytes)
            if args.verbose:
                print("Succesfully downloaded ", nextRoute)
        except Exception as e:
            if args.verbose:
                print("Something went wrong while working on path ", nextRoute)
                print(e)
                exit(-1)
            else:
                print("\nWARNING: something went wrong while working on path ", nextRoute)
                print(e)

print("Finished downloading!")
