import ftplib
import os
import ssl
import time
from pathlib import Path

# from progressbar import ProgressBar, Percentage, Bar, ETA, FileTransferSpeed
from tqdm.auto import tqdm

CACHE_PATH = (Path(__file__).parent.parent.parent / Path("cache")).resolve()


# Note: the following credentials are public (see https://www.skogsstyrelsen.se/sjalvservice/karttjanster/geodatatjanster/ftp/)
default_ftp_params = dict(
    host="ftpsks.skogsstyrelsen.se",
    port=990,
    user="SGD",
    passwd="0N!nd=I9EJ",
    timeout=15,
)


class ImplicitFTP_TLS(ftplib.FTP_TLS):
    """FTP_TLS subclass that automatically wraps sockets in SSL to support implicit FTPS."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._sock = None

    @property
    def sock(self):
        """Return the socket."""
        return self._sock

    @sock.setter
    def sock(self, value):
        """When modifying the socket, ensure that it is ssl wrapped."""
        if value is not None and not isinstance(value, ssl.SSLSocket):
            value = self.context.wrap_socket(value)
        self._sock = value


def download_from_ftp(
    filenames,
    host=default_ftp_params["host"],
    port=default_ftp_params["port"],
    user=default_ftp_params["user"],
    passwd=default_ftp_params["passwd"],
    timeout=default_ftp_params["timeout"],
):
    with ImplicitFTP_TLS() as ftps:
        print(f"Connecting to {host}.", flush=True)
        ftps.set_debuglevel(0)
        ftps.connect(host=host, port=port, timeout=timeout)  # type: ignore
        ftps.login(user=user, passwd=passwd)  # type: ignore
        ftps.prot_p()
        # print("Logged in")
        time.sleep(0.1)
        for filename in filenames:
            start_time = time.time()
            _download_single_file(filename, ftps, host)
            elapsed_time = time.time() - start_time
            if elapsed_time < 2:
                waiting_time = 2 - elapsed_time
                print(f"Waiting for {waiting_time:.2f} seconds to avoid timeout.")
                time.sleep(waiting_time)


def _download_single_file(filename, ftp, hostname):
    remotepath = Path(filename)
    localpath = CACHE_PATH / remotepath
    localpath.parent.mkdir(parents=True, exist_ok=True)

    try:
        size = ftp.size(str(remotepath))
    except ftplib.error_perm as e:
        print("File not found on remote", str(remotepath))
        raise e

    print(f"Download {str(remotepath)} from {hostname}.", flush=True)
    # widgets = [
    #     "Downloading: ",
    #     Percentage(),
    #     " ",
    #     Bar(marker="#", left="[", right="]"),
    #     " ",
    #     ETA(),
    #     " ",
    #     FileTransferSpeed(),
    # ]
    # pbar = ProgressBar(widgets=widgets, maxval=size)
    # pbar.start()
    pbar = tqdm(total=size, unit="B", unit_scale=True, unit_divisor=1024)

    try:
        with open(localpath, "wb") as fhandle:

            def _handle_file(data):
                nonlocal pbar
                fhandle.write(data)
                pbar.update(len(data))

            ftp.retrbinary(f"RETR /{str(remotepath)}", _handle_file)
            pbar.close()
    except TimeoutError:
        os.remove(localpath)
