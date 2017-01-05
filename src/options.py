from os.path import join

__version__ = "v1.3"
__configuration_path__ = "/etc/spamscope"

__defaults__ = {
    "SPAMSCOPE_CONF_PATH": __configuration_path__,
    "SPAMSCOPE_CONF_FILE": join(__configuration_path__, "spamscope.yml"),
    "SPAMSCOPE_VER": __version__, }
