# { "Depends": "py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng" }
"""
Minimal diagnostic contract -- isolates whether Address(treasury).as_hex
inside __init__ is what fails on Studio Next, independent of Datum's
larger bundle. Not part of the DATUM product; delete after diagnosis.
"""

import genlayer as gl
from genlayer.types import *


class ProbeTreasury(gl.contract.Contract):
    treasury: str

    def __init__(self, treasury: str):
        self.treasury = Address(treasury).as_hex

    @gl.public.view
    def get_treasury(self) -> str:
        return self.treasury
