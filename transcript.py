from neubanner import banner

import pprint

##############################################################################
##############################################################################


TERM = '201930'
STUDID = ['001834647']

banner.login()
banner.termset(TERM)

for ids in STUDID:
    banner.idset(banner.getxyz_studid(ids))
    data = banner.studenttranscript()

    if data is not None:
        print(data)
