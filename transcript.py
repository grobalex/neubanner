from neubanner import banner

import pprint

##############################################################################
##############################################################################

TERM = '201910'
STUDID = ['101940867','001602220','001602220','001602220','001602220','001602220','001602220']

banner.login()
banner.termset(TERM)

for ids in STUDID:
	banner.idset(banner.getxyz_studid(ids))
	data = banner.studenttranscript()

	if data is not None:
		pp = pprint.PrettyPrinter(indent=4)
		pp.pprint(data)
