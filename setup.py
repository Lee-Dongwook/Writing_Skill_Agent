"""Packaging configuration compatible with Python 3.10's bundled pip."""

from setuptools import find_namespace_packages, setup


setup(
    name="writing-feedback-agent",
    version="0.1.0",
    description="국어 비문학 요약문 첨삭을 지원하는 Supervisor 기반 에이전트",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    python_requires=">=3.10",
    package_dir={"": "src"},
    packages=find_namespace_packages(where="src"),
    include_package_data=True,
    package_data={
        "writing_feedback": ["prompts/*.md", "rubrics/*.yaml"],
    },
    install_requires=[
        "pydantic>=2.0,<3.0",
        "typing-extensions>=4.4,<5.0",
        "PyYAML>=6.0,<7.0",
    ],
    entry_points={
        "console_scripts": [
            "writing-feedback=writing_feedback.main:main",
        ],
    },
)
