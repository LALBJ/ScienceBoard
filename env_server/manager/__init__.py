from env_server.manager.ChimeraX.manager import ChimeraXManager
from env_server.manager.GrassGIS.manager import GrassGISManager
from env_server.manager.KAlgebra.manager import KAlgebraManager
from env_server.manager.TeXstudio.manager import TeXstudioManager
from env_server.manager.Celestia.manager import CelestiaManager


function_map = {
    "Celestia": CelestiaManager,
    "ChimeraX": ChimeraXManager,
    "GrassGIS": GrassGISManager,
    "KAlgebra": KAlgebraManager,
    "TeXstudio": TeXstudioManager,
}