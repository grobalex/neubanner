from __future__ import print_function

import sys
from builtins import input

from future.standard_library import install_aliases
install_aliases()
from urllib.parse import urlparse, urlencode, urljoin, parse_qs

import requests

from bs4 import BeautifulSoup

import getpass

import pickle as pk

##############################################################################
##############################################################################

_SESSION = requests.session()
_TERM = None


def login(u=None, p=None):
    global _SESSION

    r1 = _SESSION.get(
        "https://nubanner.neu.edu/ssomanager/c/SSB?pkg=twbkwbis.P_GenMenu?name=bmenu.P_MainMnu")

    soup = BeautifulSoup(r1.text, "html.parser")

    if (soup.title and soup.title.string == "Main Menu"):
        return True

    purl = urlparse(r1.url)
    form = soup.find("form")

    params = {}
    for input_field in form.find_all("input", {"type": "hidden"}):
        params[input_field["name"]] = input_field["value"]

    params["username"] = input("Login: ") if u is None else u
    params["password"] = getpass.getpass("Password: ") if p is None else p
    params["submit"] = "LOGIN"

    r2 = _SESSION.post(urljoin(purl.scheme + "://" +
                               purl.netloc, form["action"]), data=params)
    soup = BeautifulSoup(r2.text, "html.parser")

    return (soup.title and soup.title.string == "Main Menu")


def logout():
    global _SESSION
    global _TERM

    _SESSION.get("https://wl11gp.neu.edu/udcprod8/twbkwbis.P_Logout")

    _SESSION = requests.session()
    _TERM = None


def savestate():
    global _SESSION
    global _TERM

    return pk.dumps((_SESSION, _TERM))


def loadstate(s):
    global _SESSION

    _SESSION, _TERM = pk.loads(s)

##############################################################################
##############################################################################

_API_BASE = "https://wl11gp.neu.edu"


def _api(endpoint, method, params):
    global _SESSION
    global _API_BASE
    return getattr(_SESSION, method)(urljoin(_API_BASE, endpoint), data=params)


def _get(endpoint, params={}):
    return _api(endpoint, "get", params)


def _post(endpoint, params={}):
    return _api(endpoint, "post", params)

##############################################################################
##############################################################################


def _parse_select(select):
    return {option["value"]: option.string.strip() for option in select.find_all("option")}


def _parse_form(html, nohidden=False):
    retval = {"params": {}}
    soup = BeautifulSoup(html, "html.parser")

    retval["title"] = soup.title.string

    form = soup.find("div", {"class": "pagebodydiv"}).find("form")

    retval["action"] = form["action"]

    for select in form.find_all("select"):
        retval["params"][select["name"]] = _parse_select(select)

    if not nohidden:
        for hidden in form.find_all("input", {"type": "hidden"}):
            retval["params"][hidden["name"]] = hidden["value"]

    return retval

#####


def _parse_summaryclasslist(html):
    retval = []
    soup = BeautifulSoup(html, "html.parser")

    # 0=course information, 1=enrollment counts
    infotable = soup.find_all("table", {"class": "datadisplaytable"})
    if infotable:
        infotable = soup.find_all("table", {"class": "datadisplaytable"})[2]
        for student in infotable.find_all("tr")[1:]:
            info = {}
            fields = student.find_all("td")

            if (fields[2].span.find("a") is not None):
                info["name_lastfirst"] = fields[2].span.a.string
                info["xyz"] = parse_qs(
                    urlparse(fields[2].span.a["href"]).query)["xyz"][0]

            spanfields = {
                "nuid": 3,
                "regstatus": 4,
                "level": 6,
                "program": 11,
                "college": 12,
                "major": 13,
                "minor": 14,
                "concentration": 15,
            }

            offsetcheck = 8
            offset = -2

            if (fields[offsetcheck].find("a") is None):
                for k, v in spanfields.items():
                    if v > offsetcheck:
                        spanfields[k] = v + offset

            for k, v in spanfields.items():
                if (fields[v].find("span") is not None):
                    info[k] = fields[v].span.string
                else:
                    info[k] = None

            retval.append(info)

    return retval


def _parse_verifyxyz(html):
    soup = BeautifulSoup(html, "html.parser")

    result = soup.find_all("form")[1].find("input", {"name": "xyz"})
    if result is None:
        return 0
    else:
        return result["value"]


def _parse_choosexyz(html):
    soup = BeautifulSoup(html, "html.parser")
    retval = {}

    result = soup.find("select", {"name": "xyz"})
    if result:
        for opt in result.find_all("option"):
            retval[opt["value"]] = opt.string

    return retval


def _parse_studentschedule(html):
    retval = []
    soup = BeautifulSoup(html, "html.parser")

    datatables = soup.find_all("table", {"class": "datadisplaytable"})
    entry = None
    for datatable in datatables:
        if datatable.has_attr("summary"):
            if "schedule course detail" in datatable["summary"]:
                if entry is not None and "meetings" not in entry:
                    entry["meetings"] = []
                    retval.append(entry)

                entry = {"title": datatable.caption.string}

                for row in datatable.find_all("tr"):
                    acr = row.th.find("acronym")
                    if acr:
                        k = row.th.acronym.string
                    else:
                        k = row.th.string[:-1]

                    links = row.td.find_all("a")
                    if links:
                        v = [{"name": a["target"], "email":a[
                            "href"].split(":")[1]} for a in links]
                    else:
                        v = row.td.string.strip()
                    entry[k] = v
            elif "scheduled meeting times" in datatable["summary"]:
                meetings = []
                for row in datatable.find_all("tr")[1:]:
                    cols = row.find_all("td")

                    if (not cols[1].abbr) and ("Exam" not in cols[0].string):
                        meetings.append({"type": cols[5].string, "days": list(
                            cols[2].string), "times": cols[1].string.split(" - ")})

                entry["meetings"] = meetings
                retval.append(entry)

    return retval


def _parse_studentemail(html):
    soup = BeautifulSoup(html, "html.parser")
    return soup.find("table", {"class": "datadisplaytable"}).find_all("tr")[1].find_all("td")[0].text.strip()


def _parse_studenttranscript(html):
    try:
        retval = {
            "info": {},
            "transfer": [],
            "terms": [],
            "totals": {},
            "current": {
                "courses": [],
            }
        }
        soup = BeautifulSoup(html, "html.parser")

        maintable = soup.find("table", {"class": "datadisplaytable"})

        STUD_INFO = (0, 1, 2,)
        TRANSFER = "TRANSFER CREDIT ACCEPTED BY INSTITUTION"
        INST = "INSTITUTION CREDIT"
        TERM_TOTAL = "Term Totals (Undergraduate)"
        INST_TOTAL = "TRANSCRIPT TOTALS (UNDERGRADUATE)"
        PROGRESS = "COURSES IN PROGRESS"

        phase = 0
        stuff = None
        for row in maintable.find_all("tr"):
            if row.find("th", {"class": "ddtitle", }):
                if phase in STUD_INFO:
                    phase += 1

                if phase not in STUD_INFO:
                    phase = row.find("th", {"class": "ddtitle", }).find(
                        text=True, recursive=False).strip()

            if phase in STUD_INFO:
                title = row.find("th", {"class": "ddlabel"})
                if title:
                    value = row.find("td", {"class": "dddefault"})
                    if value:
                        key = title.text[:title.text.find(":")].strip()
                        value = value.text
                        if key in retval["info"]:
                            retval["info"][key].append(value)
                        else:
                            retval["info"][key] = [value]

            if phase == TRANSFER:
                th = row.find_all("th")
                td = row.find_all("td")

                if len(th) is 1 and len(td) is 1:
                    stuff = []
                    retval["transfer"].append({
                        "source": td[0].text,
                        "term": th[0].text[:th[0].text.find(":")],
                        "credits": stuff
                    })
                elif len(th) is 0 and len(td) is 7:
                    subj = td[0].text
                    course = td[1].text
                    t = td[2].text
                    credits = float(td[4].text)
                    stuff.append({
                        "subject": subj,
                        "course": course,
                        "title": t,
                        "credits": credits,
                    })

            if phase == INST:
                th = row.find_all("th")
                td = row.find_all("td")

                if row.find("span", {"class": "fieldOrangetextbold", }):
                    stuff = {
                        "term": row.text[row.text.find(":") + 1:].strip(),
                        "courses": [],
                    }
                    retval["terms"].append(stuff)
                elif len(th) is 1 and len(td) is 1:
                    key = th[0].text.strip()
                    val = td[0].text.strip()
                    stuff[key] = val
                elif len(th) is 0 and len(td) is 10:
                    subj = td[0].text
                    course = td[1].text
                    level = td[2].text
                    t = td[3].text
                    grade = td[4].text
                    credits = float(td[5].text)
                    quality = float(td[6].text)
                    stuff["courses"].append({
                        "subject": subj,
                        "course": course,
                        "level": level,
                        "title": t,
                        "grade": grade,
                        "credits": credits,
                        "quality": quality,
                    })

            if phase == TERM_TOTAL:
                if row.find("td", {"class": "ddseparator"}):
                    phase = INST
                else:
                    th = row.find_all("th")
                    td = row.find_all("td")

                    if len(th) is 1 and len(td) is 6:
                        result_type = th[0].text
                        if result_type == "Current Term:":
                            result_type = "current"
                        else:
                            result_type = "cumulative"

                        stuff[result_type] = {
                            "h_attempted": float(td[0].text.strip()),
                            "h_passed": float(td[1].text.strip()),
                            "h_earned": float(td[2].text.strip()),
                            "h_gpa": float(td[3].text.strip()),
                            "p_quality": float(td[4].text.strip()),
                            "gpa": float(td[5].text.strip()),
                        }

            if phase == INST_TOTAL:
                th = row.find_all("th")
                td = row.find_all("td")

                if len(th) is 1 and len(td) is 6:
                    result_type = th[0].text

                    if result_type == "Total Institution:":
                        result_type = "inst"
                    elif result_type == "Total Transfer:":
                        result_type = "transfer"
                    else:
                        result_type = "overall"

                    retval["totals"][result_type] = {
                        "h_attempted": float(td[0].p.text.strip()),
                        "h_passed": float(td[1].p.text.strip()),
                        "h_earned": float(td[2].p.text.strip()),
                        "h_gpa": float(td[3].p.text.strip()),
                        "p_quality": float(td[4].p.text.strip()),
                        "gpa": float(td[5].p.text.strip()),
                    }

            if phase == PROGRESS:
                th = row.find_all("th")
                td = row.find_all("td")

                if row.find("span", {"class": "fieldOrangetextbold", }):
                    retval["current"]["term"] = row.text[
                        row.text.find(":") + 1:].strip()

                if len(th) is 0 and len(td) is 6:
                    subj = td[0].text
                    course = td[1].text
                    level = td[2].text
                    t = td[3].text
                    credits = float(td[4].text)

                    retval["current"]["courses"].append({
                        "subject": subj,
                        "course": course,
                        "level": level,
                        "title": t,
                        "credits": credits,
                        "term": retval["current"]["term"]
                    })
        return retval
    except:
        return None


def _process_spanfield(span):
    contents = ""

    tag = span.next_sibling
    while True:
        if tag.name is None:
            contents += tag.strip()
        elif tag.name == "abbr":
            contents += tag.text
        elif tag.name == "a":
            contents += " <{}> ".format(tag.text)
        elif tag.name == "br":
            contents += "\n"
        elif tag.name == "span" or tag.name == "form" or tag.name == "table":
            break

        tag = tag.next_sibling

    return span.text.split(":")[0], contents.strip()


def _parse_sectionsearch(html):
    retval = []
    soup = BeautifulSoup(html, "html.parser")

    for th in soup.find_all("th", {"class": "ddtitle"}):
        td = th.parent.next_sibling.next_sibling.td

        meetings = []
        for row in td.table.find_all("tr")[1:]:
            cols = row.find_all("td")

            if (not cols[1].abbr) and ("Exam" not in cols[0].string):
                meetings.append({
                    "days": list(cols[2].string),
                    "times": cols[1].string.split(" - "),
                    "where": cols[3].string,
                    "capacity": int(cols[5].string),
                    "actual": int(cols[6].string),
                })

        splt = th.a.text.split('-')
        retval.append({
            'title': '-'.join(splt[0:-5]).strip(),
            'crn': splt[-5].strip(),
            'coursesubj': splt[-4].strip().split()[0],
            'coursenum': splt[-4].strip().split()[1],
            'section': splt[-3].strip(),
            'location': splt[-2].strip()[1:-1].strip(),
            'credits': splt[-1][9:].strip(),
            'spans': {x[0]: x[1] for x in [_process_spanfield(span) for span in td.find_all("span", {"class": "fieldlabeltext"})]},
            'meetings': meetings,
        })

    return retval

##############################################################################
##############################################################################


def _termform():
    return _parse_form(_get("/udcprod8/NEUCLSS.p_disp_dyn_sched").text)

# _ -> { term:name }


def termdict():
    return _termform()['params']['STU_TERM_IN']


def termset(term):
    global _TERM

    try:
        _post("/udcprod8/bwlkostm.P_FacStoreTerm",
              {"term": term, "name1": "bmenu.P_FacMainMnu"})
    except Exception as e:
        return 0

    _TERM = term


def _crnform():
    return _parse_form(_get("udcprod8/bwlkocrn.P_FacCrnSel").text)

# _ -> { crn:name }


def crndict():
    return _crnform()['params']['crn']


def crnset(crn):
    _post("/udcprod8/bwlkocrn.P_FacStoreCRN",
          {"crn": crn, "name1": "bmenu.P_FacMainMnu", "calling_proc_name": "P_FACENTERCRN"})

# _ -> [
# 	{ 'name_lastfirst':String or None,
# 	  'xyz':String or None,
# 	  'nuid':String or None,
#     'regstatus':String or None,
#  	  'level':String or None,
# 	  'program':String or None,
# 	  'college':String or None,
# 	  'major':String or None,
# 	  'minor':String or None,
# 	  'concentration':String or None, }
# ]


def summaryclasslist():
    return _parse_summaryclasslist(_get('/udcprod8/bwlkfcwl.P_FacClaListSum').text)

# nuid -> xyz or None


def getxyz_studid(studid, term=None):
    try:
        global _TERM
        if term is None:
            term = _TERM

        params = {
            "TERM": term,
            "CALLING_PROC_NAME": "",
            "CALLING_PROC_NAME2": "",
            "term_in": term,
            "STUD_ID": studid,
            "last_name": "",
            "first_name": "",
            "search_type": "All",  # Stu, Adv, Both, All
        }

        result = _parse_verifyxyz(
            _post("/udcprod8/bwlkoids.P_FacVerifyID", params).text)
        print(result)
        return result
    except:
        return 0


# -> { xyz:name/info }
def getxyz_name(first="", last="", stype="All", term=None):
    global _TERM
    if term is None:
        term = _TERM

    params = {
        "TERM": term,
        "CALLING_PROC_NAME": "",
        "CALLING_PROC_NAME2": "",
        "term_in": term,
        "STUD_ID": "",
        "last_name": last,  # %
        "first_name": first,  # %
        "search_type": stype,  # Stu, Adv, Both, All
    }

    return _parse_choosexyz(_post("/udcprod8/bwlkoids.P_FacVerifyID", params).text)


def idset(xyz):
    params = {
        "term_in": "",
        "sname": "bmenu.P_FacStuMnu",
        "xyz": xyz,
    }

    _post("/udcprod8/bwlkoids.P_FacStoreID", params)

# _ -> [
# 	'title': String,
#   ... : String,
#   'meetings': [ { 'type':String, 'days':[ String ], 'times':[ String ] } ]
# ]


def studentschedule():
    return _parse_studentschedule(_get('/udcprod8/bwlkfstu.P_FacStuSchd').text)

# _ -> String


def studentemail():
    return _parse_studentemail(_get('/udcprod8/bwlkosad.P_FacSelectEmalView').text)

# _ -> {
# 	Student Information...
# 	'info': { key:value }
#
# 	Current Courses...
# 	'current': {
# 		'term': String,
# 		'courses': [
#   		'course': String,
#   		'credits': #,
#   		'level': String,
#   		'subject': String,
#   		'title': String
# 		]
# 	}
#
# 	Institutional Credit...
# 	'terms': [{
# 		'Academic Standing': String,
# 		'Major': String,
# 		'Student Type': String,
# 		'term': String,
# 		'courses': [{
# 			'course': String,
# 			'credits': #,
# 			'grade': String,
# 			'level': String,
# 			'quality': #,
# 			'subject': String,
# 			'title': String
# 		}],
# 		'cumulative'/'current': {
# 			'gpa': #,
# 			'h_attempted': #,
# 			'h_earned': #,
# 			'h_gpa': #,
# 			'h_passed': #,
# 			'p_quality': #
# 		}
# 	}]
#
# 	Transfer Credit...
# 	'transfer': [{
# 		'source': String,
# 		'term': String,
# 		'credits': [{
# 			'course': String,
# 			'credits': #,
# 			'subject': String,
# 			'title': String
# 		}]
# 	}]
#
# 	Totals...
# 	'totals': {
# 		'inst'/'transfer'/'overall': {
# 			'gpa': #,
# 			'h_attempted': #,
# 			'h_earned': #,
# 			'h_gpa': #,
# 			'h_passed': #,
# 			'p_quality': #
# 		}
# 	}


def studenttranscript():
    params = {
        "levl": "",
        "tprt": "WEB",
    }

    return _parse_studenttranscript(_post("/udcprod8/bwlkftrn.P_ViewTran", params).text)

# optional -> [
# 	'title': String,
# 	'crn': String,
# 	'coursesubj': String,
# 	'coursenum': String,
# 	'section': String,
# 	'location': String,
# 	'credits': String,
# 	'spans': { String:String },
# 	'meetings': [ { 'days':[ String ], 'times': [ String ], 'where': String, actual: #, capacity: # } ],
# ]


def sectionsearch(
        term=None, crn="",
        subject=("%",),
        coursenum="", coursetitle="",
        attribute=("%",), level=("%",),
        seats=False,
        schedule=("%",), instruction=("%",),
        creditfrom="", creditto="",
        campus=("%",), termpart=("%",),
        instructor=("%",),
        begin_hh="0", begin_mi="0", begin_ap="a",
        end_hh="0", end_mi="0", end_ap="a",
        sel_day=tuple([])):

    global _TERM
    if term is None:
        term = _TERM

    params = [
        ("sel_day", "dummy"),
        ("STU_TERM_IN", term),
        ("sel_subj", "dummy"),
        ("sel_attr", "dummy"),
        ("sel_schd", "dummy"),
        ("sel_camp", "dummy"),
        ("sel_insm", "dummy"),
        ("sel_ptrm", "dummy"),
        ("sel_levl", "dummy"),
        ("sel_instr", "dummy"),
        ("sel_seat", "dummy"),
        ("p_msg_code", "UNSECURED"),
        ("sel_crn", crn),
        ("sel_crse", coursenum),
        ("sel_title", coursetitle),
        ("sel_from_cred", creditfrom),
        ("sel_to_cred", creditto),
        ("begin_hh", end_hh),
        ("begin_mi", end_mi),
        ("begin_ap", end_ap),
        ("end_hh", end_hh),
        ("end_mi", end_mi),
        ("end_ap", end_ap),
    ]

    if seats:
        params.append(("sel_seat", "Y"))

    to_add = {
        "sel_subj": subject,
        "sel_attr": attribute,
        "sel_levl": level,
        "sel_schd": schedule,
        "sel_insm": instruction,
        "sel_camp": campus,
        "sel_ptrm": termpart,
        "sel_instr": instructor,
        "sel_day": sel_day,
    }

    for key, source in to_add.items():
        for s in source:
            params.append((key, s))

    return _parse_sectionsearch(_post("/udcprod8/NEUCLSS.p_class_search", params).text)

# _ -> { param:{ code:val } }


def searchcodes(term=None):
    global _TERM
    if term is None:
        term = _TERM

    params = [
        ("p_msg_code", "UNSECURED"),
        ("STU_TERM_IN", term)
    ]

    return _parse_form(_post("/udcprod8/NEUCLSS.p_class_select", params).text, nohidden=True)['params']
