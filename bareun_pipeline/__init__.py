"""
bareun-pipeline — bareun 형태소 분석기 비동기 파이프라인
"""
from .pipeline import AnalysisResult, BatchResult, BareunPipeline
from .dict_manager import DictManager
from .extractor import extract_nouns

__version__ = "0.1.0"
__all__ = [
    "BareunPipeline",
    "DictManager",
    "AnalysisResult",
    "BatchResult",
    "extract_nouns",
]
