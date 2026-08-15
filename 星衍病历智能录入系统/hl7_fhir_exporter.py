#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HL7/FHIR 数据导出模块
支持将病历数据导出为标准的 HL7 v2.x 和 FHIR R4 格式
"""
import json
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Dict, List, Optional


class HL7Exporter:
    """HL7 v2.x 导出器"""
    
    def __init__(self):
        self.field_separator = "|"
        self.component_separator = "^"
        self.repetition_separator = "~"
        self.escape_character = "\\"
        self.subcomponent_separator = "&"
    
    def export_adt(self, patient_data: Dict) -> str:
        """
        导出 ADT（患者管理）消息
        :param patient_data: 患者数据字典
        :return: HL7消息字符串
        """
        segments = []
        
        # MSH - 消息头
        msh = self._build_msh_segment("ADT", "A01")  # A01 = 入院
        segments.append(msh)
        
        # EVN - 事件类型
        evn = self._build_evn_segment(patient_data.get("admit_date", ""))
        segments.append(evn)
        
        # PID - 患者标识
        pid = self._build_pid_segment(patient_data)
        segments.append(pid)
        
        # PV1 - 患者就诊信息
        pv1 = self._build_pv1_segment(patient_data)
        segments.append(pv1)
        
        return "\r".join(segments)
    
    def export_orm(self, order_data: Dict) -> str:
        """
        导出 ORM（医嘱）消息
        :param order_data: 医嘱数据字典
        :return: HL7消息字符串
        """
        segments = []
        
        # MSH - 消息头
        msh = self._build_msh_segment("ORM", "O01")  # O01 = 医嘱请求
        segments.append(msh)
        
        # PID - 患者标识
        pid = self._build_pid_segment(order_data.get("patient", {}))
        segments.append(pid)
        
        # ORC - 通用医嘱
        orc = self._build_orc_segment(order_data)
        segments.append(orc)
        
        # OBR - 观察请求
        obr = self._build_obr_segment(order_data)
        segments.append(obr)
        
        return "\r".join(segments)
    
    def _build_msh_segment(self, message_type: str, trigger_event: str) -> str:
        """构建MSH段"""
        now = datetime.now().strftime("%Y%m%d%H%M%S")
        return self.field_separator.join([
            "MSH",
            self.field_separator + self.component_separator + self.repetition_separator + 
            self.escape_character + self.subcomponent_separator,
            "星衍AI",  # 发送应用
            "医疗系统",  # 发送设施
            "",  # 接收应用
            "",  # 接收设施
            now,  # 日期/时间
            "",  # 安全性
            f"{message_type}^{trigger_event}",  # 消息类型
            f"MSG{now}",  # 消息控制ID
            "P",  # 处理ID
            "2.4",  # 版本ID
        ])
    
    def _build_evn_segment(self, event_date: str) -> str:
        """构建EVN段"""
        if not event_date:
            event_date = datetime.now().strftime("%Y%m%d%H%M%S")
        return self.field_separator.join([
            "EVN",
            "A01",  # 事件类型代码
            event_date,  # 事件日期/时间
            "",  # 事件原因
        ])
    
    def _build_pid_segment(self, patient_data: Dict) -> str:
        """构建PID段"""
        return self.field_separator.join([
            "PID",
            "1",  # 设置ID
            "",  # 患者ID（外部）
            patient_data.get("patient_id", ""),  # 患者ID（内部）
            "",  # 备用患者ID
            f"{patient_data.get('name', '')}^^^^^^",  # 患者姓名
            "",  # 母亲姓名
            patient_data.get("birth_date", ""),  # 出生日期
            patient_data.get("gender", ""),  # 性别
            "",  # 患者别名
            f"{patient_data.get('address', '')}^^^^^^",  # 地址
            "",  # 县代码
            patient_data.get("phone", ""),  # 电话号码
            "",  # 工作电话
            "",  # 主要语言
            "",  # 婚姻状况
            "",  # 宗教
            patient_data.get("patient_id", ""),  # 患者账号
            "",  # SSN号
        ])
    
    def _build_pv1_segment(self, patient_data: Dict) -> str:
        """构建PV1段"""
        return self.field_separator.join([
            "PV1",
            "1",  # 设置ID
            "I" if patient_data.get("inpatient") else "O",  # 患者类别（I=住院，O=门诊）
            "",  # 患者位置
            "",  # 就诊类型
            patient_data.get("attending_doctor", ""),  # 主治医生
            "",  # 转诊医生
            "",  # 咨询医生
            "",  # 医院服务
            patient_data.get("admit_date", ""),  # 入院日期
            patient_data.get("discharge_date", ""),  # 出院日期
            "",  # 临时费用
            "",  # 就诊费用
            "",  # 就诊时长
            "",  # 就诊号
        ])
    
    def _build_orc_segment(self, order_data: Dict) -> str:
        """构建ORC段"""
        return self.field_separator.join([
            "ORC",
            "NW",  # 医嘱控制代码（NW=新）
            order_data.get("order_id", ""),  # 医嘱控制号
            "",  # 填写者医嘱号
            "",  # 状态
            "",  # 响应标志
            "",  # 数量/时间
            "",  # 执行者
            "",  # 医嘱开始日期/时间
            "",  # 医嘱结束日期/时间
        ])
    
    def _build_obr_segment(self, order_data: Dict) -> str:
        """构建OBR段"""
        return self.field_separator.join([
            "OBR",
            "1",  # 设置ID
            "",  # 填写者医嘱号
            order_data.get("test_code", ""),  # 通用服务ID
            order_data.get("test_name", ""),  # 观察描述
            "",  # 观察日期/时间
            "",  # 数量
            "",  # 单位
            "",  # 结果状态
        ])


class FHIRExporter:
    """FHIR R4 导出器"""
    
    def export_patient(self, patient_data: Dict) -> Dict:
        """
        导出患者资源
        :param patient_data: 患者数据字典
        :return: FHIR Patient资源
        """
        resource = {
            "resourceType": "Patient",
            "id": patient_data.get("patient_id", ""),
            "identifier": [
                {
                    "system": "http://hospital.org/patient-id",
                    "value": patient_data.get("patient_id", "")
                }
            ],
            "active": True,
            "name": [
                {
                    "use": "official",
                    "family": "",
                    "given": [patient_data.get("name", "")]
                }
            ],
            "gender": patient_data.get("gender", "unknown"),
            "birthDate": patient_data.get("birth_date", ""),
            "telecom": [
                {
                    "system": "phone",
                    "value": patient_data.get("phone", ""),
                    "use": "home"
                }
            ],
            "address": [
                {
                    "use": "home",
                    "text": patient_data.get("address", "")
                }
            ]
        }
        
        return resource
    
    def export_encounter(self, encounter_data: Dict) -> Dict:
        """
        导出就诊资源
        :param encounter_data: 就诊数据字典
        :return: FHIR Encounter资源
        """
        resource = {
            "resourceType": "Encounter",
            "id": encounter_data.get("encounter_id", ""),
            "status": "finished",
            "class": {
                "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
                "code": "IMP" if encounter_data.get("inpatient") else "AMB"
            },
            "subject": {
                "reference": f"Patient/{encounter_data.get('patient_id', '')}"
            },
            "period": {
                "start": encounter_data.get("admit_date", ""),
                "end": encounter_data.get("discharge_date", "")
            },
            "participant": [
                {
                    "type": [
                        {
                            "coding": [
                                {
                                    "system": "http://terminology.hl7.org/CodeSystem/v3-ParticipationType",
                                    "code": "PPRF"
                                }
                            ]
                        }
                    ],
                    "individual": {
                        "reference": f"Practitioner/{encounter_data.get('doctor_id', '')}",
                        "display": encounter_data.get("doctor_name", "")
                    }
                }
            ]
        }
        
        return resource
    
    def export_condition(self, condition_data: Dict) -> Dict:
        """
        导出病情资源
        :param condition_data: 病情数据字典
        :return: FHIR Condition资源
        """
        resource = {
            "resourceType": "Condition",
            "id": condition_data.get("condition_id", ""),
            "clinicalStatus": {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                        "code": "active"
                    }
                ]
            },
            "verificationStatus": {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
                        "code": "confirmed"
                    }
                ]
            },
            "code": {
                "coding": [
                    {
                        "system": "http://snomed.info/sct",
                        "code": condition_data.get("icd_code", ""),
                        "display": condition_data.get("diagnosis", "")
                    }
                ],
                "text": condition_data.get("diagnosis", "")
            },
            "subject": {
                "reference": f"Patient/{condition_data.get('patient_id', '')}"
            },
            "encounter": {
                "reference": f"Encounter/{condition_data.get('encounter_id', '')}"
            },
            "onsetDateTime": condition_data.get("onset_date", ""),
            "recordedDate": condition_data.get("recorded_date", "")
        }
        
        return resource
    
    def export_medication_request(self, medication_data: Dict) -> Dict:
        """
        导出药物请求资源
        :param medication_data: 药物数据字典
        :return: FHIR MedicationRequest资源
        """
        resource = {
            "resourceType": "MedicationRequest",
            "id": medication_data.get("request_id", ""),
            "status": "active",
            "intent": "order",
            "medicationCodeableConcept": {
                "coding": [
                    {
                        "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
                        "code": medication_data.get("drug_code", ""),
                        "display": medication_data.get("drug_name", "")
                    }
                ],
                "text": medication_data.get("drug_name", "")
            },
            "subject": {
                "reference": f"Patient/{medication_data.get('patient_id', '')}"
            },
            "encounter": {
                "reference": f"Encounter/{medication_data.get('encounter_id', '')}"
            },
            "authoredOn": medication_data.get("prescribed_date", ""),
            "requester": {
                "reference": f"Practitioner/{medication_data.get('doctor_id', '')}"
            },
            "dosageInstruction": [
                {
                    "text": medication_data.get("dosage", ""),
                    "timing": {
                        "repeat": {
                            "frequency": medication_data.get("frequency", 1),
                            "period": medication_data.get("period", 1),
                            "periodUnit": "d"
                        }
                    },
                    "route": {
                        "coding": [
                            {
                                "system": "http://snomed.info/sct",
                                "code": medication_data.get("route_code", "26643006"),
                                "display": medication_data.get("route", "口服")
                            }
                        ]
                    }
                }
            ]
        }
        
        return resource
    
    def export_bundle(self, resources: List[Dict]) -> Dict:
        """
        导出Bundle资源（资源集合）
        :param resources: 资源列表
        :return: FHIR Bundle资源
        """
        bundle = {
            "resourceType": "Bundle",
            "type": "collection",
            "timestamp": datetime.now().isoformat(),
            "entry": []
        }
        
        for resource in resources:
            bundle["entry"].append({
                "fullUrl": f"urn:uuid:{resource.get('id', '')}",
                "resource": resource
            })
        
        return bundle


class MedicalRecordConverter:
    """病历数据转换器"""
    
    def __init__(self):
        self.hl7_exporter = HL7Exporter()
        self.fhir_exporter = FHIRExporter()
    
    def convert_to_hl7(self, record_data: Dict, message_type: str = "ADT") -> str:
        """
        将病历数据转换为HL7格式
        :param record_data: 病历数据
        :param message_type: 消息类型（ADT/ORM等）
        :return: HL7消息字符串
        """
        if message_type == "ADT":
            return self.hl7_exporter.export_adt(record_data)
        elif message_type == "ORM":
            return self.hl7_exporter.export_orm(record_data)
        else:
            raise ValueError(f"不支持的消息类型: {message_type}")
    
    def convert_to_fhir(self, record_data: Dict) -> Dict:
        """
        将病历数据转换为FHIR格式
        :param record_data: 病历数据
        :return: FHIR Bundle资源
        """
        resources = []
        
        # 转换患者信息
        if "patient" in record_data:
            patient_resource = self.fhir_exporter.export_patient(record_data["patient"])
            resources.append(patient_resource)
        
        # 转换就诊信息
        if "encounter" in record_data:
            encounter_resource = self.fhir_exporter.export_encounter(record_data["encounter"])
            resources.append(encounter_resource)
        
        # 转换诊断信息
        if "conditions" in record_data:
            for condition in record_data["conditions"]:
                condition_resource = self.fhir_exporter.export_condition(condition)
                resources.append(condition_resource)
        
        # 转换药物信息
        if "medications" in record_data:
            for medication in record_data["medications"]:
                medication_resource = self.fhir_exporter.export_medication_request(medication)
                resources.append(medication_resource)
        
        # 创建Bundle
        bundle = self.fhir_exporter.export_bundle(resources)
        
        return bundle
    
    def export_to_file(self, record_data: Dict, format: str, output_path: str):
        """
        导出到文件
        :param record_data: 病历数据
        :param format: 格式（hl7/fhir-json/fhir-xml）
        :param output_path: 输出文件路径
        """
        if format == "hl7":
            hl7_message = self.convert_to_hl7(record_data)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(hl7_message)
        
        elif format == "fhir-json":
            fhir_bundle = self.convert_to_fhir(record_data)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(fhir_bundle, f, ensure_ascii=False, indent=2)
        
        elif format == "fhir-xml":
            fhir_bundle = self.convert_to_fhir(record_data)
            # 简单的JSON转XML（实际应使用专门的FHIR XML序列化库）
            root = ET.Element("Bundle")
            root.set("xmlns", "http://hl7.org/fhir")
            
            # 这里只是示例，实际需要完整的FHIR XML序列化
            json_str = json.dumps(fhir_bundle, ensure_ascii=False)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(f"<!-- FHIR XML export -->\n{json_str}")
        
        else:
            raise ValueError(f"不支持的格式: {format}")


if __name__ == "__main__":
    # 测试示例
    converter = MedicalRecordConverter()
    
    # 示例病历数据
    sample_record = {
        "patient": {
            "patient_id": "P001",
            "name": "张三",
            "gender": "male",
            "birth_date": "1980-01-15",
            "phone": "13800138000",
            "address": "北京市朝阳区"
        },
        "encounter": {
            "encounter_id": "E001",
            "patient_id": "P001",
            "inpatient": False,
            "admit_date": "2026-08-15",
            "discharge_date": "2026-08-16",
            "doctor_id": "D001",
            "doctor_name": "李医生"
        },
        "conditions": [
            {
                "condition_id": "C001",
                "patient_id": "P001",
                "encounter_id": "E001",
                "icd_code": "J18.9",
                "diagnosis": "肺炎",
                "onset_date": "2026-08-14",
                "recorded_date": "2026-08-15"
            }
        ],
        "medications": [
            {
                "request_id": "M001",
                "patient_id": "P001",
                "encounter_id": "E001",
                "drug_code": "Amoxicillin",
                "drug_name": "阿莫西林",
                "dosage": "500mg",
                "frequency": 3,
                "period": 1,
                "route": "口服",
                "route_code": "26643006",
                "prescribed_date": "2026-08-15",
                "doctor_id": "D001"
            }
        ]
    }
    
    # 导出HL7
    hl7_message = converter.convert_to_hl7(sample_record)
    print("=== HL7 Message ===")
    print(hl7_message[:200] + "...")
    
    # 导出FHIR JSON
    fhir_bundle = converter.convert_to_fhir(sample_record)
    print("\n=== FHIR Bundle ===")
    print(json.dumps(fhir_bundle, ensure_ascii=False, indent=2)[:500] + "...")
    
    # 导出到文件
    converter.export_to_file(sample_record, "hl7", "test.hl7")
    converter.export_to_file(sample_record, "fhir-json", "test.fhir.json")
    print("\n✅ 导出完成")
