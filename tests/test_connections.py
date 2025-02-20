import pytest

from skogdata.ftp import ImplicitFTP_TLS


# @pytest.mark.skip(reason="not overload ftp server")
def test_connection_sgd():
    host = "ftpsks.skogsstyrelsen.se"
    port = 990
    user = "SGD"
    passwd = "0N!nd=I9EJ"  # Note: this password is publicly available at https://www.skogsstyrelsen.se/sjalvservice/karttjanster/geodatatjanster/ftp/
    _timeout_ = 30
    with ImplicitFTP_TLS() as ftps:
        ftps.set_debuglevel(0)
        ftps.connect(host=host, port=port, timeout=_timeout_)
        ftps.login(user=user, passwd=passwd)
        ftps.prot_p()
