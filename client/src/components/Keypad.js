import "./Keypad.scss";
import Axios from "axios";
import React, { useState, useEffect } from "react";

const Keypad = () => {
    const [robotName, setRobotName] = useState("SeRo01");
    const [serviceMode, setServiceMode] = useState("감시 모드");
    const [correctPassWord, setcorrectPassWord] = useState("");
    const [password, setPassWord] = useState("");
    let pw = "";

    const handleClickNumber = (e, dots) => {
        e.preventDefault();
        e.target.classList.add("grow");
        dots[pw.length].classList.add("active");
        
        pw += e.currentTarget.innerText;
        if (pw.length >= 4) {
            setPassWord(pw);
            pw = "";
        }
    }

    useEffect(() => {
        const Initializing = async () => {
            const resPreferences = await Axios.get("./document/preferences.json");
    
            if (resPreferences.status === 200) {
                if (resPreferences.data.SERVICE_MODE === "Inspection") {
                    setServiceMode("감시 모드");
                } else {
                    setServiceMode("방역 모드");
                }
                setRobotName(resPreferences.data.ROBOT_NAME);
                setcorrectPassWord(resPreferences.data.PASSWORD);
                console.log(resPreferences.data);
            }
        }

        Initializing();

        let dots = Array.from(document.getElementsByClassName("secure__dot"));
        let keys = Array.from(document.getElementsByClassName("secure__key"));
        let clickEvent = e => handleClickNumber(e, dots);

        keys.forEach((_, idx) => {
            keys[idx].addEventListener("mousedown", clickEvent);

            if (password.length === 4) {
                console.log(password, correctPassWord);
                if (password === correctPassWord) {
                    dots.forEach((_, jdx) => {
                        dots[jdx].classList.add("correct");
                    })                    
                } else {
                    dots.forEach((_, jdx) => {
                        dots[jdx].classList.add("wrong");
                    })
                }

                setTimeout(function() {
                    dots.forEach(dot => dot.className = "secure__dot");
                }, 900);
            }
        })

        return () => {
            for (let i = 0; i < keys.length; i++) {
                if (keys[i]) {
                    keys[i].removeEventListener("mousedown", handleClickNumber);
                }
            }
        }
    }, [password])

    return (
        <div className="password__ctrl">
            <div className="secure__top">
                <div className="robot__name">로봇</div>
                <div className="robot__tag">{robotName}</div>
                <div className="robot__service">{serviceMode}</div>
            </div>
            <div className="secure__middle">
                <p>관리자 암호를 입력해주세요</p>
                <div className="secure__dots">
                    <div className="secure__dot"></div>
                    <div className="secure__dot"></div>
                    <div className="secure__dot"></div>
                    <div className="secure__dot"></div>
                </div>
            </div>
            <div className="secure__bottom">
                <div className="secure__key__contianer">
                    <div className="secure__key">1</div>
                    <div className="secure__key">2</div>
                    <div className="secure__key">3</div>
                </div>
                <div className="secure__key__contianer">
                    <div className="secure__key">4</div>
                    <div className="secure__key">5</div>
                    <div className="secure__key">6</div>
                </div>
                <div className="secure__key__contianer">
                    <div className="secure__key">7</div>
                    <div className="secure__key">8</div>
                    <div className="secure__key">9</div>
                </div>
            </div>
        </div>
    )
}

export default Keypad;