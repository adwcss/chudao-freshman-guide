"""Legacy adapter: local evidence only; never load received credentials."""
from backend.answer import Answerer
from backend.retriever.retriever import Retriever
from backend.settings import ROOT, Settings


def stream_answer(question):
    answerer = Answerer(Retriever(ROOT), Settings())
    prepared = answerer.prepare(question, [])
    answer, _ = answerer.generate(question, prepared)
    yield answer
