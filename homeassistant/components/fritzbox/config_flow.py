"""Config flow for AVM Fritz!Box."""
from urllib.parse import urlparse

from pyfritzhome import Fritzhome, LoginError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.ssdp import ATTR_SSDP_LOCATION, ATTR_UPNP_FRIENDLY_NAME
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

# pylint:disable=unused-import
from .const import DEFAULT_HOST, DEFAULT_USERNAME, DOMAIN

DATA_SCHEMA_USER = vol.Schema(
    {
        vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
        vol.Required(CONF_USERNAME, default=DEFAULT_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

DATA_SCHEMA_CONFIRM = vol.Schema(
    {
        vol.Required(CONF_USERNAME, default=DEFAULT_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

RESULT_AUTH_FAILED = "auth_failed"
RESULT_NOT_FOUND = "not_found"
RESULT_SUCCESS = "success"


class FritzboxConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a AVM Fritz!Box config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167

    def __init__(self):
        """Initialize flow."""
        self._host = None
        self._manufacturer = None
        self._model = None
        self._name = None
        self._password = None
        self._username = None

    def _get_entry(self):
        return self.async_create_entry(
            title=self._name,
            data={
                CONF_HOST: self._host,
                CONF_PASSWORD: self._password,
                CONF_USERNAME: self._username,
            },
        )

    def _try_connect(self):
        """Try to connect and check auth."""
        fritzbox = Fritzhome(
            host=self._host, user=self._username, password=self._password
        )
        try:
            fritzbox.login()
            fritzbox.logout()
            return RESULT_SUCCESS
        except OSError:
            return RESULT_NOT_FOUND
        except LoginError:
            return RESULT_AUTH_FAILED

    async def async_step_import(self, user_input=None):
        """Handle configuration by yaml file."""
        return await self.async_step_user(user_input)

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:

            for entry in self.hass.config_entries.async_entries(DOMAIN):
                if entry.data.get(CONF_HOST) == user_input[CONF_HOST]:
                    if entry.data != user_input:
                        self.hass.config_entries.async_update_entry(
                            entry, data=user_input
                        )
                    return self.async_abort(reason="already_configured")

            self._host = user_input[CONF_HOST]
            self._name = user_input[CONF_HOST]
            self._password = user_input[CONF_PASSWORD]
            self._username = user_input[CONF_USERNAME]

            result = await self.hass.async_add_executor_job(self._try_connect)

            if result == RESULT_SUCCESS:
                return self._get_entry()
            if result != RESULT_AUTH_FAILED:
                return self.async_abort(reason=result)
            errors["base"] = result

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA_USER, errors=errors
        )

    async def async_step_ssdp(self, user_input):
        """Handle a flow initialized by discovery."""
        host = urlparse(user_input[ATTR_SSDP_LOCATION]).hostname
        self.context[CONF_HOST] = host

        for progress in self._async_in_progress():
            if progress.get("context", {}).get(CONF_HOST) == host:
                return self.async_abort(reason="already_in_progress")

        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if entry.data.get(CONF_HOST) == host:
                if entry.data != user_input:
                    self.hass.config_entries.async_update_entry(entry, data=user_input)
                return self.async_abort(reason="already_configured")

        self._host = host
        self._name = user_input[ATTR_UPNP_FRIENDLY_NAME]

        self.context["title_placeholders"] = {"name": self._name}
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input=None):
        """Handle user-confirmation of discovered node."""
        errors = {}

        if user_input is not None:
            self._password = user_input[CONF_PASSWORD]
            self._username = user_input[CONF_USERNAME]
            result = await self.hass.async_add_executor_job(self._try_connect)

            if result == RESULT_SUCCESS:
                return self._get_entry()
            if result != RESULT_AUTH_FAILED:
                return self.async_abort(reason=result)
            errors["base"] = result

        return self.async_show_form(
            step_id="confirm",
            data_schema=DATA_SCHEMA_CONFIRM,
            description_placeholders={"name": self._name},
            errors=errors,
        )
