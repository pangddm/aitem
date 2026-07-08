from __future__ import annotations


import re

from app.memory.graph.schema import (
    NodeType
)



class EntityNormalizer:


    """
    Kubernetes Entity标准化


    输入:

    [
        "deployment.apps/nginx",
        "nginx deployment",
        "Deployment/nginx"
    ]


    输出:

    [
        "Deployment/nginx"
    ]

    """



    def normalize(

        self,

        entities: list[str],

    ) -> list[str]:


        result = set()



        for entity in entities:


            normalized = (

                self._normalize_one(

                    entity

                )

            )


            if normalized:


                result.add(normalized)



        return list(result)



    def _normalize_one(

        self,

        entity: str,

    ) -> str | None:


        entity = entity.strip()


        if not entity:

            return None



        entity_lower = entity.lower()



        # ======================
        # Deployment
        # ======================


        if (

            "deployment" in entity_lower

            or "deploy" in entity_lower

        ):


            name = self._extract_name(

                entity

            )


            if name:


                return (

                    f"{NodeType.DEPLOYMENT.value}"

                    f"/{name}"

                )



        # ======================
        # Pod
        # ======================


        if "pod" in entity_lower:


            name = self._extract_name(

                entity

            )


            if name:


                return (

                    f"{NodeType.POD.value}"

                    f"/{name}"

                )



        # ======================
        # Namespace
        # ======================


        if "namespace" in entity_lower:


            name = self._extract_name(

                entity

            )


            if name:


                return (

                    f"{NodeType.NAMESPACE.value}"

                    f"/{name}"

                )



        # ======================
        # Node
        # ======================


        if (

            "node" in entity_lower

        ):


            name = self._extract_name(

                entity

            )


            if name:


                return (

                    f"{NodeType.NODE.value}"

                    f"/{name}"

                )



        # ======================
        # Fault
        # ======================


        fault_keywords = [

            "crashloopbackoff",

            "oomkilled",

            "imagepullbackoff",

            "pending",

            "failed",

            "error",

        ]


        for keyword in fault_keywords:


            if keyword in entity_lower:


                return (

                    f"{NodeType.FAULT.value}"

                    f"/{keyword}"

                )



        # ======================
        # 普通实体
        # ======================


        return entity



    def _extract_name(

        self,

        text: str,

    ) -> str | None:


        """
        提取:

        Deployment/nginx

        deployment.apps/nginx

        pod nginx-xxx

        """


        patterns = [


            r"/([\w\-\.]+)",


            r"\s([\w\-\.]+)$",


        ]



        for pattern in patterns:


            match = re.search(

                pattern,

                text

            )


            if match:


                return (

                    match.group(1)

                    .strip()

                )



        return None