"""FastAPI application for the dashboard: ``uvicorn f1lab.api.main:app``.

Every endpoint lives under ``/api`` and is read-only. The dashboard calls the API
through the Vite dev server proxy, so no CORS setup is needed. Interactive docs:
``/docs``.
"""

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, FastAPI, Query, Request, status
from fastapi.responses import JSONResponse

from f1lab import __version__
from f1lab.api.schemas import (
    CircuitSummary,
    Health,
    RaceDetail,
    RaceSimulation,
    RaceSummary,
    ScSensitivity,
    StrategyComparison,
    TyreModel,
)
from f1lab.api.service import Lab, NotFoundError
from f1lab.config import API_PREFIX, SENSITIVITY_RUNS, SIM_RUNS, get_db_path
from f1lab.sim.setup import SetupError
from f1lab.sim.strategy import StrategyError

Strategies = Annotated[
    list[str] | None,
    Query(alias="strategy", description="Alternative strategy, e.g. M-25-H; repeatable"),
]


def _error_handler(code: int) -> Callable[[Request, Exception], Awaitable[JSONResponse]]:
    async def handle(_request: Request, error: Exception) -> JSONResponse:
        return JSONResponse(status_code=code, content={"detail": str(error)})

    return handle


def create_app(
    db_path: Path | None = None,
    *,
    runs: int = SIM_RUNS,
    sensitivity_runs: int = SENSITIVITY_RUNS,
) -> FastAPI:
    """Build the API on top of a database.

    Args:
        db_path: SQLite database (default: ``<data dir>/f1lab.sqlite``).
        runs: Monte Carlo runs per race and per compared strategy.
        sensitivity_runs: Runs per point of the Safety Car sensitivity curve.

    Returns:
        The application; the database is opened on the first request.
    """
    lab = Lab(db_path or get_db_path(), runs=runs, sensitivity_runs=sensitivity_runs)
    app = FastAPI(
        title="F1 Strategy Lab API",
        version=__version__,
        summary="Races, tyre models and Monte Carlo strategy simulations for the dashboard.",
    )
    router = APIRouter(prefix=API_PREFIX)

    @router.get("/health")
    def health() -> Health:
        """Liveness check."""
        return Health(status="ok", version=__version__)

    @router.get("/races")
    def races() -> list[RaceSummary]:
        """All races in the database and whether the simulator can run them."""
        return lab.races()

    @router.get("/races/{race_id}")
    def race(race_id: int) -> RaceDetail:
        """A race with its starters, results and strategies."""
        return lab.race(race_id)

    @router.get("/races/{race_id}/simulation")
    def simulation(race_id: int) -> RaceSimulation:
        """Monte Carlo of the race with the strategies actually run, next to the real result."""
        return lab.simulation(race_id)

    @router.get("/races/{race_id}/strategies")
    def strategies(race_id: int, driver: str, strategy: Strategies = None) -> StrategyComparison:
        """A driver's actual strategy against up to two alternatives."""
        return lab.compare(race_id, driver, tuple(strategy or ()))

    @router.get("/races/{race_id}/sc-sensitivity")
    def sc_sensitivity(race_id: int, driver: str, strategy: Strategies = None) -> ScSensitivity:
        """The same strategies with Safety Cars rarer or more frequent than usual."""
        return lab.sensitivity(race_id, driver, tuple(strategy or ()))

    @router.get("/circuits")
    def circuits() -> list[CircuitSummary]:
        """Circuits with a tyre model."""
        return lab.circuits()

    @router.get("/circuits/{circuit_id}/tyres")
    def tyres(circuit_id: str) -> TyreModel:
        """Degradation model of a circuit and the observed laps behind it."""
        return lab.tyres(circuit_id)

    app.include_router(router)
    app.add_exception_handler(NotFoundError, _error_handler(status.HTTP_404_NOT_FOUND))
    for error in (SetupError, StrategyError):
        app.add_exception_handler(error, _error_handler(status.HTTP_422_UNPROCESSABLE_CONTENT))
    return app


app = create_app()
