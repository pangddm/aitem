from enum import Enum



class NodeType(str, Enum):

    """
    Neo4j节点类型
    """


    USER = "User"


    MEMORY = "Memory"


    ENTITY = "Entity"


    REASON = "Reason"



    # Kubernetes对象

    CLUSTER = "Cluster"


    NAMESPACE = "Namespace"


    NODE = "Node"


    POD = "Pod"


    DEPLOYMENT = "Deployment"


    REPLICASET = "ReplicaSet"


    STATEFULSET = "StatefulSet"


    DAEMONSET = "DaemonSet"


    JOB = "Job"


    CRONJOB = "CronJob"


    SERVICE = "Service"


    ENDPOINTS = "Endpoints"


    INGRESS = "Ingress"


    CONTAINER = "Container"


    CONFIGMAP = "ConfigMap"


    SECRET = "Secret"


    # RBAC

    ROLE = "Role"


    CLUSTERROLE = "ClusterRole"


    ROLEBINDING = "RoleBinding"


    CLUSTERROLEBINDING = "ClusterRoleBinding"


    SERVICEACCOUNT = "ServiceAccount"


    GROUP = "Group"


    CLUSTERUSER = "ClusterUser"


    # 存储

    PVC = "PersistentVolumeClaim"


    PV = "PersistentVolume"


    STORAGECLASS = "StorageClass"



    # 故障相关

    FAULT = "Fault"


    ERROR = "Error"


    ALERT = "Alert"



    # 资源

    IMAGE = "Image"

    # 审计日志

    OPERATION = "Operation"




class RelationType(str, Enum):


    """
    Neo4j关系类型
    """


    # 用户Memory


    HAS_MEMORY = "HAS_MEMORY"



    # Memory关联实体


    MENTIONS = "MENTIONS"



    RELATED_TO = "RELATED_TO"



    # K8s关系


    RUNS_IN = "RUNS_IN"


    RUNS_ON = "RUNS_ON"



    BELONGS_TO = "BELONGS_TO"



    USES = "USES"



    DEPENDS_ON = "DEPENDS_ON"



    EXPOSES = "EXPOSES"

    CHANGED_BY = "CHANGED_BY"

    CHANGED_TO = "CHANGED_TO"

    OPERATED_ON = "OPERATED_ON"

    PERFORMED = "PERFORMED"

    GRANTS = "GRANTS"


    ASSIGNED_TO = "ASSIGNED_TO"


    SELECTS = "SELECTS"

    BACKS = "BACKS"

    # 故障关系


    HAS_FAULT = "HAS_FAULT"



    CAUSED_BY = "CAUSED_BY"



    OCCURRED_ON = "OCCURRED_ON"



    RESOLVED_BY = "RESOLVED_BY"



    SIMILAR_TO = "SIMILAR_TO"


    REPLACED_BY = "REPLACED_BY"


    SUPERSEDED_BY = "SUPERSEDED_BY"