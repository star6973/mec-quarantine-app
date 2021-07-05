from datetime import datetime, timedelta
import dateutil.parser

receive_arrivals_data = [
    {
        "flightId":"KE123",
        "airline":"대한항공",
        "scheduleDateTime":"0010",
        "estimatedDateTime":"0010",
        "remark":"착륙",
        "airportCode":"AKL",
        "terminalId":"P03",
        "airport":"오클랜드",
        "gatenumber":"247",
        "carousel":"11",
        "exitnumber":"A",
        "elapsetime":"1220"
    },
    {
        "flightId":"KE678",
        "airline":"대한항공",
        "scheduleDateTime":"0020",
        "estimatedDateTime":"0020",
        "remark":"착륙",
        "airportCode":"CDG",
        "terminalId":"P03",
        "airport":"파리",
        "gatenumber":"247",
        "carousel":"11",
        "exitnumber":"A",
        "elapsetime":"1220"
    }
]
