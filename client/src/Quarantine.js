import "./Quarantine.scss";
import * as Image from "./Image";
import Axios from "axios";
import { useEffect, useState } from "react";
import { LottieControl } from "./Common";

function ChangeImage ({ delay, pageList }) {
    const [image, setImage] = useState(Image.ProtectList[0]);
    const useImage = pageList.filter(item => item["use"] === true);
    let useImageBox = [];

    Image.ProtectList.forEach(list => {
        useImage.forEach((k, v) => {
            if (list.split("/")[3].split(".")[0] === k.image.split(".")[0]) {
                useImageBox.push(list)
            }
        })
    });

    useEffect(() => {
        let idx = 1;
        const intervalID = setInterval(async () => {
            setImage(useImageBox[idx]);
            idx = (idx + 1) % useImageBox.length;            
        }, delay);

        return () => {
            clearInterval(intervalID);
        }
    }, []);
    
    return (
        <img src={image} alt="quarantine_img" />
    )
}

function Quarantine ({ status }) {
    const [delay, setDelay] = useState(1000);
    const [pageList, setPageList] = useState({});
    const [language, setLanguage] = useState([]);

    useEffect(() => {
        const Initializing = async () => {
            const resConfig = await Axios.get("./document/config.json");
            const resLanguage = await Axios.get("./document/language.json");
    
            if (resConfig.status === 200 && resLanguage.status === 200) {
                setDelay(resConfig.data.SPEAK_INTERVAL);
                setPageList(resConfig.data.IMAGE_SPEAK_ITEM);
                setLanguage(resLanguage.data.list);
            }
        }

        // initializing config.json & language.json
        Initializing();
    }, [])
    
	return (
        <div className="quarantine__ctrl">
			{
                Object.keys(pageList).length !== 0 && Object.keys(language).length !== 0 ?
                    status === "moving" ?
                        <div className="quarantine__move">
                            <div className="quarantine__title">{ language["TEXT/QUARANTINE/MOVE_TITLE"] }</div>
                            <div className="quarantine__title__sub">{ language["TEXT/QUARANTINE/MOVE_SUB_TITLE"] }</div>
                            <LottieControl loop={ true } autoplay={ true } data={ Image.Moving } />
                        </div>
                    :
                        <div className="quarantine__service">
                            <ChangeImage delay={ delay } pageList={ pageList } />
                        </div>
                :
                    <>페이지 로딩 중</>
            }
        </div>
    )
}

export default Quarantine;