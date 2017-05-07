from PyQt5 import QtNetwork
from PyQt5.QtCore import QUrl, QUrlQuery
from request import ApiListRequest


class Api(object):
    MAX_PAGE_SIZE = 10000

    def __init__(self, manager):
        self._manager = manager

    def _query(self, endpt, params):
        url = QUrl(endpt)
        query = QUrlQuery()
        for key in params:
            query.addQueryItem(key, str(params[key]))
        url.setQuery(query)
        return url

    def _get(self, endpoint, params={}):
        req = QtNetwork.QNetworkRequest()
        query = self._query(endpoint, params)
        return self._manager.get(query, req)

    def _getPage(self, endpoint, pagesize, pagenum, params={}):
        params["page[size]"] = pagesize
        params["page[number]"] = pagenum
        return self._get(endpoint, params)

    def _getMany(self, endpoint, count, params={}):
        def getReqs():
            for i in range(1, count + 1):
                yield self._getPage(QUrl(endpoint), count, i, params)
        return ApiListRequest(getReqs(), count)

    def _getAll(self, endpoint, params={}):
        return self._getMany(endpoint, self.MAX_PAGE_SIZE, params)

    def _post(self, endpoint, data):
        req = QtNetwork.QNetworkRequest()
        return self._manager.post(QUrl(endpoint), req, data)
