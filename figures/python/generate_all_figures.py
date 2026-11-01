from figure_01_lifecycle import main as figure_01
from figure_02_ingestion_physical_state import main as figure_02
from figure_03_metadata_scaling import main as figure_03
from figure_04_query_elasticities import main as figure_04
from figure_05_temporal_break_even import main as figure_05


def main() -> None:
    for function in (figure_01, figure_02, figure_03, figure_04, figure_05):
        function()


if __name__ == "__main__":
    main()

