import "./Quarantine.css";
import * as Image from "./Image";
import { useEffect, useState } from "react";
import { LottieControl } from "./Common";

function ChangeImage({timeout}) {
    const [state, setState] = useState(Image.Protect0);

    useEffect (() => {
        const pageList = [Image.Protect0, Image.Protect1, Image.Protect2];
        let idx = 1;
        const intervalID = setInterval(() => {
            setState(pageList[idx])
            idx = (idx + 1) % pageList.length;
        }, timeout);

        return () => {
            clearInterval(intervalID);
        }
    }, [])

    return (
        <img src={state} alt="quarantine_img" />
    )
}

function Quarantine() {
    const [state, setState] = useState("quaranting");

	return (
        <div className="quar__ctrl">
			{
                state === "moving" ?
                    <div className="quar__mv">
                        <div className="quar__title">Move To POI</div>
                        <LottieControl loop={true} autoplay={true} data={Image.Moving} />
                    </div>
                :
                    <div className="quar__sv">
                        <ChangeImage timeout={5000} />
                    </div>
            }
        </div>
    )
}

export default Quarantine;