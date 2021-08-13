import "./Quarantine.css";
import * as Image from "./Image";
import Axios from "axios";
import { useEffect, useState } from "react";
import { LottieControl } from "./Common";

function ChangeImage ({ delay, pageList }) {
    const [image, setImage] = useState(Image.ProtectList[0]);
    const useImage = pageList.filter(item => item["use"] === true);
    let useImageBox = [];

    Image.ProtectList.forEach(item => {
        useImage.forEach((k, v) => {
            if (item.split("/")[3].split(".")[0] === k.image.split(".")[0]) {
                useImageBox.push(item)
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
            const res_config = await Axios.get("./document/config.json");
            const res_lang = await Axios.get("./document/language.json");
    
            if (res_config.status === 200 && res_lang.status === 200) {
                setDelay(res_config.data.SPEAK_INTERVAL);
                setPageList(res_config.data.IMAGE_SPEAK_ITEM);
                setLanguage(res_lang.data.list);
            }
        }

        // initializing config.json & language.json
        Initializing()
    }, [])
    
	return (
        <div className="quar__ctrl">
			{
                Object.keys(pageList).length !== 0 && Object.keys(language).length !== 0 ?
                    status === "moving" ?
                        <div className="quar__mv">
                            <div className="quar__title">{language["TEXT/QUARANTINE/MOVE_TITLE"]}</div>
                            <div className="quar__title__sub">{language["TEXT/QUARANTINE/MOVE_SUB_TITLE"]}</div>
                            <LottieControl loop={true} autoplay={true} data={Image.Moving} />
                        </div>
                    :
                        <div className="quar__sv">
                            <ChangeImage delay={delay} pageList={pageList} />
                        </div>
                :
                    <>페이지 로딩 중</>
            }
        </div>
    )
}

export default Quarantine;