from collections import namedtuple

import pytest

from pyhamilton.interface import (
    HamiltonInterface,
    HamiltonResponse,
    HamiltonResponseStatus,
    HamiltonStepError,
    HamiltonReturnParseError,
    HardwareError,
    ImproperDispensationError,
    InvalidErrCodeError,
)

TEST_DATA_TYPE = namedtuple(
    "TEST_DATA_TYPE", "id data fields return_data parsed_result expected_exception"
)
TEST_DATA = [
    # 0
    TEST_DATA_TYPE(
        "Server response is empty",
        '{"command": "STAR-return", "step-name": "command-1", "step-return1": "", "step-return2": "", "step-return3": "", "step-return4": "", "id": "1" }',
        None,
        None,
        None,
        HamiltonStepError,
    ),
    # 1
    TEST_DATA_TYPE(
        "Server response contains spaces",
        '{"command": "STAR-return", "step-name": "command-1", "step-return1": "    ", "step-return2": "", "step-return3": "", "step-return4": "", "id": "1" }',
        None,
        None,
        None,
        HamiltonStepError,
    ),
    # 2
    TEST_DATA_TYPE(
        "Server response with command failed str value",
        '{"command": "STAR-return", "step-name": "command-1", "step-return1": "0", "step-return2": "", "step-return3": "", "step-return4": "", "id": "1" }',
        None,
        None,
        None,
        HamiltonStepError,
    ),
    # 3
    TEST_DATA_TYPE(
        "Server response with command failed num value",
        '{"command": "STAR-return", "step-name": "command-1", "step-return1": 0, "step-return2": "", "step-return3": "", "step-return4": "", "id": "1" }',
        None,
        None,
        None,
        HamiltonStepError,
    ),
    # 4
    TEST_DATA_TYPE(
        "Server response with command failed and bad return format",
        '{"command": "STAR-return", "step-name": "command-1", "step-return1": "1[0,1,2,4[5,6,7", "step-return2": "", "step-return3": "", "step-return4": "", "id": "1" }',
        None,
        None,
        None,
        HamiltonReturnParseError,
    ),
    # 5
    TEST_DATA_TYPE(
        "Server response with command succeeded",
        '{"command": "STAR-return", "step-name": "command-1", "step-return1": 1, "step-return2": "", "step-return3": "", "step-return4": "", "id": "1" }',
        None,
        None,
        None,
        None,
    ),
    # 6
    TEST_DATA_TYPE(
        "Server response with command succeeded and extra data",
        '{"command": "STAR-return", "step-name": "command-1", "step-return1": "0[0,1,2,4,[5,6,7", "step-return2": "", "step-return3": "", "step-return4": "", "id": "1" }',
        None,
        None,
        None,
        HamiltonReturnParseError,
    ),
    # 7
    TEST_DATA_TYPE(
        "one string field is requested",
        '{"command": "STAR-return", "step-name": "command-1", "step-return1": "0[0,1,2,4[5,6,7", "step-return2": "", "step-return3": "", "step-return4": "", "id": "1" }',
        "step-return1",
        ["0[0,1,2,4[5,6,7"],
        None,
        HamiltonReturnParseError,
    ),
    # 8
    TEST_DATA_TYPE(
        "one list field is requested",
        '{"command": "STAR-return", "step-name": "command-1", "step-return1": "0[0,1,2,4,A[5,6,7", "step-return2": "", "step-return3": "", "step-return4": "", "id": "1" }',
        ["step-return1"],
        ["0[0,1,2,4,A[5,6,7"],
        None,
        HamiltonReturnParseError,
    ),
    # 8
    TEST_DATA_TYPE(
        "field not in server response is requested",
        '{"command": "STAR-return", "step-name": "command-1", "step-return1": "0[0,1,2,4[5,6,7", "step-return2": "", "step-return3": "", "step-return4": "", "id": "1" }',
        "step-return11",
        [],
        None,
        HamiltonReturnParseError,
    ),
    # 9
    TEST_DATA_TYPE(
        "multiple available fields are requested",
        '{"command": "STAR-return", "step-name": "command-1", "step-return1": "0[0,1,2,4[5,6,7", "step-return2": 3, "step-return3": "", "step-return4": "", "id": "1" }',
        ["step-return1", "step-return2"],
        ["0[0,1,2,4[5,6,7", 3],
        None,
        HamiltonReturnParseError,
    ),
    # 10
    TEST_DATA_TYPE(
        "multiple (avail+not available) fields are requested",
        '{"command": "STAR-return", "step-name": "command-1", "step-return1": "0[0,1,2,4[5,6,7", "step-return2": "100", "step-return3": "", "step-return4": "", "id": "1" }',
        ["step-return2", "step-return12"],
        ["100"],
        None,
        HamiltonReturnParseError,
    ),
    # 11
    TEST_DATA_TYPE(
        "result is made of one block",
        '{"command": "STAR-return", "step-name": "command-1", "step-return1": "0[01,00,00,0,,Cos_96_DW_1mL_0002,A1", "id": "1" }',
        None,
        None,
        None,
        None,
    ),
    # 12
    TEST_DATA_TYPE(
        "result is made of multiple blocks",
        '{"command": "STAR-return", "step-name": "command-1", "step-return1": "0[01,00,00,0,0.0,HT_L_0001,1[02,00,00,0,0.0,HT_L_0001,2[03,00,00,0,0.0,HT_L_0001,3", "id": "1" }',
        None,
        None,
        None,
        None,
    ),
    # 13
    TEST_DATA_TYPE(
        "step-return1 == 2",
        '{"command": "STAR-return", "step-name": "command-1", "step-return1": "2", "id": "1" }',
        None,
        None,
        None,
        HamiltonStepError,
    ),
    # 14
    TEST_DATA_TYPE(
        "no global error while block report one",
        '{"command": "STAR-return", "step-name": "command-1", "step-return1": "0[01,02,00,0,,Cos_96_DW_1mL_0002,A1", "id": "1" }',
        None,
        None,
        None,
        HardwareError,
    ),
    # 15
    TEST_DATA_TYPE(
        "global error while blocks report no error",
        '{"command": "STAR-return", "step-name": "command-1", "step-return1": "1[01,00,00,0,,Cos_96_DW_1mL_0002,A1,[02,00,00,0,,Cos_96_DW_1mL_0003,A2", "id": "1" }',
        None,
        None,
        None,
        HamiltonReturnParseError,
    ),
    # 16
    TEST_DATA_TYPE(
        "block error field is not a number",
        '{"command": "STAR-return", "step-name": "command-1", "step-return1": "1[01,AB,00,0,,Cos_96_DW_1mL_0002,A1", "id": "1" }',
        None,
        None,
        None,
        HamiltonReturnParseError,
    ),
    # 17
    TEST_DATA_TYPE(
        "dispense error is reported",
        '{"command": "STAR-return", "step-name": "command-1", "step-return1": "1[01,105,00,0,,Cos_96_DW_1mL_0002,A1", "id": "1" }',
        None,
        None,
        None,
        ImproperDispensationError,
    ),
    # 18
    TEST_DATA_TYPE(
        "block error is invalid number",
        '{"command": "STAR-return", "step-name": "command-1", "step-return1": "0[01,999,00,0,,Cos_96_DW_1mL_0002,A1", "id": "1" }',
        None,
        None,
        None,
        InvalidErrCodeError,
    ),
]


class Test_HamiltonInterface:
    @pytest.mark.parametrize(
        "server_response,expected_response",
        [
            pytest.param(
                TEST_DATA[0].data,
                HamiltonResponse(
                    status=HamiltonResponseStatus.UNKNOWN, raw=TEST_DATA[0].data
                ),
                id=TEST_DATA[0].id,
            ),
            pytest.param(
                TEST_DATA[1].data,
                HamiltonResponse(
                    status=HamiltonResponseStatus.UNKNOWN, raw=TEST_DATA[1].data
                ),
                id=TEST_DATA[1].id,
            ),
            pytest.param(
                TEST_DATA[2].data,
                HamiltonResponse(
                    status=HamiltonResponseStatus.FAILED, raw=TEST_DATA[2].data
                ),
                id=TEST_DATA[2].id,
            ),
            pytest.param(
                TEST_DATA[3].data,
                HamiltonResponse(
                    status=HamiltonResponseStatus.FAILED, raw=TEST_DATA[3].data
                ),
                id=TEST_DATA[3].id,
            ),
            pytest.param(
                TEST_DATA[4].data,
                HamiltonResponse(
                    status=HamiltonResponseStatus.FAILED, raw=TEST_DATA[4].data
                ),
                id=TEST_DATA[4].id,
            ),
            pytest.param(
                TEST_DATA[5].data,
                HamiltonResponse(
                    status=HamiltonResponseStatus.SUCCESS, raw=TEST_DATA[5].data
                ),
                id=TEST_DATA[5].id,
            ),
            pytest.param(
                TEST_DATA[6].data,
                HamiltonResponse(
                    status=HamiltonResponseStatus.SUCCESS, raw=TEST_DATA[6].data
                ),
                id=TEST_DATA[6].id,
            ),
        ],
    )
    def test_parse_response_status_when_(
        self, mocker, server_response, expected_response
    ):
        mocker.patch("pyhamilton.interface.HamiltonInterface.start", return_value=None)
        mocker.patch("pyhamilton.interface.HamiltonInterface.stop", return_value=None)

        hamiltonInterface = HamiltonInterface()
        response = hamiltonInterface.parse_response(server_response=server_response)
        assert response == expected_response

    @pytest.mark.parametrize(
        "server_response,fields,expected_response",
        [
            pytest.param(
                TEST_DATA[7].data,
                TEST_DATA[7].fields,
                HamiltonResponse(
                    status=HamiltonResponseStatus.SUCCESS,
                    return_data=TEST_DATA[7].return_data,
                    raw=TEST_DATA[7].data,
                ),
                id=TEST_DATA[7].id,
            ),
            pytest.param(
                TEST_DATA[8].data,
                TEST_DATA[8].fields,
                HamiltonResponse(
                    status=HamiltonResponseStatus.SUCCESS,
                    return_data=TEST_DATA[8].return_data,
                    raw=TEST_DATA[8].data,
                ),
                id=TEST_DATA[8].id,
            ),
            pytest.param(
                TEST_DATA[9].data,
                TEST_DATA[9].fields,
                HamiltonResponse(
                    status=HamiltonResponseStatus.SUCCESS,
                    return_data=TEST_DATA[9].return_data,
                    raw=TEST_DATA[9].data,
                ),
                id=TEST_DATA[9].id,
            ),
            pytest.param(
                TEST_DATA[10].data,
                TEST_DATA[10].fields,
                HamiltonResponse(
                    status=HamiltonResponseStatus.SUCCESS,
                    moduleID="3",
                    return_data=TEST_DATA[10].return_data,
                    raw=TEST_DATA[10].data,
                ),
                id=TEST_DATA[10].id,
            ),
            pytest.param(
                TEST_DATA[11].data,
                TEST_DATA[11].fields,
                HamiltonResponse(
                    status=HamiltonResponseStatus.SUCCESS,
                    moduleID="100",
                    return_data=TEST_DATA[11].return_data,
                    raw=TEST_DATA[11].data,
                ),
                id=TEST_DATA[11].id,
            ),
        ],
    )
    def test_parse_response_return_data_when_(
        self, mocker, server_response, fields, expected_response
    ):
        mocker.patch("pyhamilton.interface.HamiltonInterface.start", return_value=None)
        mocker.patch("pyhamilton.interface.HamiltonInterface.stop", return_value=None)

        hamiltonInterface = HamiltonInterface()
        response = hamiltonInterface.parse_response(
            server_response=server_response, return_data=fields
        )
        assert response == expected_response

    @pytest.mark.parametrize(
        "server_response,expected_response",
        [
            pytest.param(
                TEST_DATA[12].data,
                HamiltonResponse(
                    status=HamiltonResponseStatus.SUCCESS,
                    parsed_return=[
                        {
                            "numField": 1,
                            "mainErrField": 0,
                            "slaveErr": 0,
                            "recoveryBtnId": 0,
                            "stepData": " ",
                            "labwareName": "Cos_96_DW_1mL_0002",
                            "labwarePos": "A1",
                        }
                    ],
                    raw=TEST_DATA[12].data,
                ),
                id=TEST_DATA[12].id,
            ),
            pytest.param(
                TEST_DATA[13].data,
                HamiltonResponse(
                    status=HamiltonResponseStatus.SUCCESS,
                    parsed_return=[
                        {
                            "numField": 1,
                            "mainErrField": 0,
                            "slaveErr": 0,
                            "recoveryBtnId": 0,
                            "stepData": "0.0",
                            "labwareName": "HT_L_0001",
                            "labwarePos": "1",
                        },
                        {
                            "numField": 2,
                            "mainErrField": 0,
                            "slaveErr": 0,
                            "recoveryBtnId": 0,
                            "stepData": "0.0",
                            "labwareName": "HT_L_0001",
                            "labwarePos": "2",
                        },
                        {
                            "numField": 3,
                            "mainErrField": 0,
                            "slaveErr": 0,
                            "recoveryBtnId": 0,
                            "stepData": "0.0",
                            "labwareName": "HT_L_0001",
                            "labwarePos": "3",
                        },
                    ],
                    raw=TEST_DATA[13].data,
                ),
                id=TEST_DATA[13].id,
            ),
        ],
    )
    def test_parse_response_parsed_result_when_(
        self, mocker, server_response, expected_response
    ):
        mocker.patch("pyhamilton.interface.HamiltonInterface.start", return_value=None)
        mocker.patch("pyhamilton.interface.HamiltonInterface.stop", return_value=None)

        hamiltonInterface = HamiltonInterface()
        response = hamiltonInterface.parse_response(server_response=server_response)
        assert response == expected_response

    @pytest.mark.parametrize(
        "server_response,expected_exception",
        [
            pytest.param(
                TEST_DATA[2].data,
                TEST_DATA[2].expected_exception,
                id=TEST_DATA[2].id,
            ),
            pytest.param(
                TEST_DATA[4].data,
                TEST_DATA[4].expected_exception,
                id=TEST_DATA[4].id,
            ),
            pytest.param(
                TEST_DATA[14].data,
                TEST_DATA[14].expected_exception,
                id=TEST_DATA[14].id,
            ),
            pytest.param(
                TEST_DATA[15].data,
                TEST_DATA[15].expected_exception,
                id=TEST_DATA[15].id,
            ),
            pytest.param(
                TEST_DATA[16].data,
                TEST_DATA[16].expected_exception,
                id=TEST_DATA[16].id,
            ),
            pytest.param(
                TEST_DATA[17].data,
                TEST_DATA[17].expected_exception,
                id=TEST_DATA[17].id,
            ),
            pytest.param(
                TEST_DATA[18].data,
                TEST_DATA[18].expected_exception,
                id=TEST_DATA[18].id,
            ),
        ],
    )
    def test_parse_response_raise_exception_when_(
        self, mocker, server_response, expected_exception
    ):
        mocker.patch("pyhamilton.interface.HamiltonInterface.start", return_value=None)
        mocker.patch("pyhamilton.interface.HamiltonInterface.stop", return_value=None)

        hamiltonInterface = HamiltonInterface()
        with pytest.raises(expected_exception):
            hamiltonInterface.parse_response(server_response=server_response, raise_first_exception=True)
