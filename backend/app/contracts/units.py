from typing import Annotated

from pydantic import Field

SCHEDULING_TZ = "America/Chicago"

Id = Annotated[str, Field(min_length=1)]
Minutes = Annotated[int, Field(ge=0, description="Integer minutes")]
Days = Annotated[int, Field(ge=0, description="Whole days")]
KWh = Annotated[float, Field(description="Energy, kWh")]
KW = Annotated[float, Field(ge=0, description="Power, kW")]
UsdPerMWh = Annotated[float, Field(description="Price, USD/MWh")]
Usd = Annotated[float, Field(description="Value, USD")]
Fraction = Annotated[float, Field(ge=0, le=1)]
