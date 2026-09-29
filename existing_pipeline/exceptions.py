class PipelineModuleMissingError(RuntimeError):
    """
    Raised by a stub module in existing_pipeline/ when it is actually
    invoked. These stubs exist only so the FastAPI app can import the
    `core` package tree and boot without crashing -- they must be replaced
    with the real, original source files before layout generation will
    produce correct (or any) output.

    This is deliberately NOT swallowed anywhere upstream: routes/services
    convert it into a 501 NOT_IMPLEMENTED API error rather than pretending
    to succeed, per the "do not invent missing engineering logic" rule.
    """

    def __init__(self, module_name: str, symbol: str):
        self.module_name = module_name
        self.symbol = symbol
        super().__init__(
            f"'{symbol}' in existing_pipeline/{module_name} is a placeholder stub. "
            f"The real {module_name} was not part of the uploaded project and has not "
            f"been provided yet. Replace backend/existing_pipeline/{module_name} with "
            f"the original file from the source project to enable this operation."
        )
