"""A notebook which renders cells one cell at a time."""

import logging
from typing import TYPE_CHECKING, Optional

from prompt_toolkit.cache import FastDictCache
from prompt_toolkit.layout.containers import (
    ConditionalContainer,
    DynamicContainer,
    VSplit,
    Window,
)
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.widgets import Box
from upath import UPath

from euporie.core.config import add_setting
from euporie.core.tabs.notebook import BaseNotebook
from euporie.core.widgets.cell import Cell
from euporie.core.widgets.page import PrintingContainer

if TYPE_CHECKING:
    from os import PathLike
    from typing import Callable, Dict, Optional

    from prompt_toolkit.layout.containers import AnyContainer

    from euporie.core.app import BaseApp

log = logging.getLogger(__name__)


class PreviewNotebook(BaseNotebook):
    """A notebook tab which renders cells sequentially."""

    def __init__(
        self, app: "Optional[BaseApp]" = None, path: "Optional[PathLike]" = None
    ):
        """Create a new instance."""
        super().__init__(app, path)
        self.cell_index = 0
        self.app.before_render += self.before_render
        self.app.after_render += self.after_render
        self.cells = FastDictCache(get_value=self.get_cell)
        self.running = False
        self.ran_cells = set()

        # If we are running the notebook, pause rendering util the kernel has started
        if self.app.config.run:
            self.app.pause_rendering()
            self.kernel.start(self.kernel_started, wait=True)

    def print_title(self) -> "None":
        from euporie.core.formatted_text.utils import (
            FormattedTextAlign,
            add_border,
            align,
            wrap,
        )

        width = self.app.output.get_size().columns
        ft = [("bold", self.path.name)]
        ft = wrap(ft, width - 4)
        ft = align(FormattedTextAlign.CENTER, ft, width=width - 4)
        ft = add_border(ft, width=width)
        self.app.print_text(ft)

    def kernel_started(self, result: "Optional[Dict]" = None) -> "None":
        """Resumes rendering the app when the kernel has started."""
        self.app.resume_rendering()

    def close(self, cb: "Optional[Callable]" = None) -> "None":
        """Clean up render hooks before the tab is closed."""
        self.app.after_render -= self.after_render
        if self.app.config.run and self.app.config.save:
            self.save()
        super().close(cb)

    def before_render(self, app: "BaseApp") -> "None":
        """Run the cell before rendering it if needed."""
        if (
            self.app.tab == self
            and self.cell_index == 0
            and self.app.config.show_filenames
        ):
            self.print_title()

        if self.app.config.run:
            cell = self.cell()
            cell.run_or_render(wait=True)
            self.kernel.wait_for_status("idle")

    def after_render(self, app: "BaseApp") -> "None":
        """Close the tab if all cells have been rendered."""
        if self.app.tab == self:
            if self.cell_index < len(self.json["cells"]) - 1:
                self.cell_index += 1
            else:
                app.close_tab(self)

    def get_cell(self, index: "int") -> "Cell":
        """Render a cell by its index."""
        return Cell(index, self.json["cells"][index], self)

    def cell(self) -> "AnyContainer":
        """Return the current cell."""
        return self.cells[(self.cell_index,)]

    def load_container(self) -> "AnyContainer":
        """Abscract method for loading the notebook's main container."""
        # return DynamicContainer(lambda: PrintingContainer([self.cell()]))
        print(self.app.config.max_notebook_width)
        return PrintingContainer(
            [
                VSplit(
                    [
                        ConditionalContainer(
                            Window(), filter=~self.app.config.filter("expand")
                        ),
                        Box(
                            body=DynamicContainer(lambda: self.cell()),
                            padding=0,
                            width=Dimension(
                                preferred=self.app.config.max_notebook_width
                            ),
                        ),
                        ConditionalContainer(
                            Window(), filter=~self.app.config.filter("expand")
                        ),
                    ]
                )
            ]
        )

    # ################################### Settings ####################################

    add_setting(
        name="run",
        flags=["--run"],
        type_=bool,
        help_="Run the notebook files when loaded",
        default=False,
        description="""
            If set, notebooks will be run automatically when opened, or if previewing a
            file, the notebooks will be run before being output.
        """,
    )

    add_setting(
        name="save",
        flags=["--save"],
        type_=bool,
        help_="Save the notebook after running it",
        default=False,
        description="""
            If set, notebooks will be saved after they have been run. This setting only
            has any affect if the :option:`run` setting is active.
        """,
    )

    add_setting(
        name="show_filenames",
        flags=["--show-filenames"],
        type_=bool,
        help_="Show the notebook filenames when previewing multiple notebooks",
        default=False,
        description="""
            If set, the notebook filenames will be printed above each notebook's output
            when multiple notebooks are being previewed.
        """,
    )
