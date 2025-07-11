from env_server.eval.TeXstudio.eval import TeXstudioEval
from env_server.eval.KAlgebra.eval import KAlgebraEval
from env_server.eval.GrassGIS.eval import GrassGISEval
from env_server.eval.ChimeraX.eval import ChimeraXEval
from env_server.eval.Celestia.eval import CelestiaEval


function_map = {
    "Celestia": CelestiaEval,
    "ChimeraX": ChimeraXEval,
    "GrassGIS": GrassGISEval,
    "KAlgebra": KAlgebraEval,
    "TeXstudio": TeXstudioEval
}