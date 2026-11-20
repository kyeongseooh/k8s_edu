"""Compile a two-step KFP v2 pipeline without contacting a cluster."""
import argparse
from kfp import compiler, dsl
from kfp.dsl import Artifact, Input, Output


@dsl.component(base_image='python:3.11-slim')
def make_report(report: Output[Artifact], name: str = 'learner'):
    from pathlib import Path
    p = Path(report.path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f'hello, {name}\n', encoding='utf-8')
    report.metadata['format'] = 'text/plain'


@dsl.component(base_image='python:3.11-slim')
def read_report(report: Input[Artifact]) -> str:
    from pathlib import Path
    text = Path(report.path).read_text(encoding='utf-8').strip()
    print(text)
    return text


@dsl.pipeline(name='edu-artifact-report')
def pipeline(name: str = 'learner'):
    produced = make_report(name=name)
    read_report(report=produced.outputs['report'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('output', help='Output path, e.g. /tmp/edu-ir.yaml')
    compiler.Compiler().compile(pipeline, parser.parse_args().output)
